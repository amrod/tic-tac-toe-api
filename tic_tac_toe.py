# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

from __future__ import division
import logging

import endpoints
from google.appengine.ext import ndb
from protorpc import remote, messages, message_types
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import User, Game, Score, RankingForms, RankingForm
from models import (
    StringMessage,
    GameForm,
    GameForms,
    MakeMoveForm,
    ScoreForms,
    UserNameForm
)
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(UserNameForm)
JOIN_GAME_REQUEST = endpoints.ResourceContainer(
    UserNameForm,
    urlsafe_game_key=messages.StringField(1),
)
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1),
)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),
)
USER_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1),
    email=messages.StringField(2)
)
GET_USER_GAMES_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1)
)


MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID


@endpoints.api(name='tic_tac_toe',
               version='v1',
               allowed_client_ids=[API_EXPLORER_CLIENT_ID])
class TicTacToeApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                    'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        return StringMessage(message='User {} created!'.format(
                request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        player1 = User.query(User.name == request.player_1).get()

        if not player1:
            raise endpoints.NotFoundException(
                    'No user named "{}" was found.'.format(request.player_1))

        player2 = User.query(User.name == request.player_2).get()

        if request.player_2 and not player2:
            raise endpoints.NotFoundException(
                    'No user named "{}" was found.'.format(request.player_1))

        try:
            game = Game.new_game(player1.key, player2.key if player2 else None)
        except ValueError:
            raise endpoints.BadRequestException('**Some error**')

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        #taskqueue.add(url='/tasks/cache_average_attempts')

        return game.to_form('Good luck playing Tic Tac Toe!')

    @endpoints.method(request_message=JOIN_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}/join',
                      name='join_game',
                      http_method='PUT')
    def join_game(self, request):
        """Joins user to game as player2"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        game = get_by_urlsafe(request.urlsafe_game_key, Game)

        if not game:
            raise endpoints.NotFoundException('Game not found!')

        if user.key == game.player1:
            raise endpoints.BadRequestException(
                'Player #2 cannot be the same as Player #1.')

        if game.player2:
            raise endpoints.BadRequestException(
                'Game is already full!')
        try:
            game.set_player2(user.key)
        except ValueError as err:
            raise endpoints.BadRequestException(err.message)

        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        #taskqueue.add(url='/tasks/cache_average_attempts')

        return game.to_form('Good luck playing Tic Tac Toe!')

    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
                return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}/move',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""

        game = get_by_urlsafe(request.urlsafe_game_key, Game)

        if game.game_over:
            return game.to_form('Game already over!')

        if not game.player2:
            raise endpoints.NotFoundException('Waiting for player 2 to join.')

        user = User.query(User.name == request.user_name).get()

        if not user:
            raise endpoints.NotFoundException('User "{}" does not exist.'
                                              .format(request.user_name))

        if user.key not in (game.player1, game.player2):
            raise endpoints.BadRequestException('User "{}" not in this game.'
                                                .format(request.user_name))

        if game.next_turn != user.key:
            raise endpoints.BadRequestException("It's not your turn!")

        cell = getattr(game, 'cell_{}'.format(request.position))

        if cell is None:
            raise endpoints.BadRequestException('Cell #{} does not exist.'
                                                .format(request.position))
        elif cell != -1:
            raise endpoints.BadRequestException('Cell #{} is already occupied.'
                                                .format(request.position))

        game.set_position(request.position, user.key)
        game.next_turn = game.player2 if game.player1 == user.key else game.player1

        symbol = TicTacToeApi.check_for_win(game=game)
        if symbol > -1:
            game.end_game(winner=user.key)
            return game.to_form('You won!')

        game.put()

        return game.to_form()

    @staticmethod
    def check_for_win(game):
        grid = game.grid

        for i in range(3):
            if grid[i][0] == grid[i][1] and grid[i][0] == grid[i][2]:
                return grid[i][0]
            if grid[0][i] == grid[1][i] and grid[0][i] == grid[2][i]:
                return grid[0][i]

        if grid[0][0] == grid[1][1] and grid[0][0] == grid[2][2]:
            return grid[0][0]

        if grid[2][0] == grid[1][1] and grid[2][0] == grid[0][2]:
            return grid[2][0]

        return -1

    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        return ScoreForms(items=[score.to_form() for score in Score.query()])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        scores = Score.query(ancestor=user.key)
        return ScoreForms(items=[score.to_form() for score in scores])

    # @endpoints.method(response_message=StringMessage,
    #                   path='games/average_attempts',
    #                   name='get_average_attempts_remaining',
    #                   http_method='GET')
    # def get_average_attempts(self, request):
    #     """Get the cached average moves remaining"""
    #     return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')
    #
    # @staticmethod
    # def _cache_average_attempts():
    #     """Populates memcache with the average moves remaining of Games"""
    #     games = Game.query(Game.game_over == False).fetch()
    #     if games:
    #         count = len(games)
    #         total_attempts_remaining = sum([game.attempts_remaining
    #                                         for game in games])
    #         average = float(total_attempts_remaining)/count
    #         memcache.set(MEMCACHE_MOVES_REMAINING,
    #                      'The average moves remaining is {:.2f}'.format(average))

    @endpoints.method(request_message=GET_USER_GAMES_REQUEST,
                      response_message=GameForms,
                      path='games/user/{user_name}',
                      http_method='GET')
    def get_user_games(self, request):
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException('A User with that name does not exist!')

        games = Game.query(Game.player1 == user.key).fetch()
        if games:
            return GameForms(items=[game.to_form() for game in games])
        else:
            raise endpoints.NotFoundException('User {} has not created any games.'
                                              ''.format(request.user_name))

    @endpoints.method(request_message=endpoints.ResourceContainer(urlsafe_game_key=messages.StringField(1)),
                      response_message=StringMessage,
                      path='game/{urlsafe_game_key}/cancel',
                      http_method='PUT')
    def cancel_game(self, request):
        game = get_by_urlsafe(request.urlsafe_game_key, Game)

        if not game:
            raise endpoints.NotFoundException('That game does not exist!')

        if game.game_over:
            raise endpoints.BadRequestException('Game cannot be cancelled because it is already over.')
        else:
            game.cancel_game()

        return StringMessage(message='Game cancelled.')

    @endpoints.method(request_message=message_types.VoidMessage,
                      response_message=RankingForms,
                      path='user/rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        # TODO: Fetch all Score entities first, then collate users from them.
        # @ndb.tasklet
        # def callback(user):
        #     score = yield Score.query_user(user.key).fetch_async()
        #     raise ndb.Return(score)

        # scores = User.query().order(User.name).map(callback)

        scores = Score.query().fetch()

        performance = {}

        for score in scores:

            if score.winner in performance:
                ranking = performance[score.winner]
                ranking['wins'] += 1
                ranking['avg_moves'] += (
                    (score.winner_moves - ranking['avg_moves']) /
                    ranking['wins'])
            else:
                performance[score.winner] = {
                    'name': score.get_winner_name(), 'wins': 1, 'losses': 0,
                    'avg_moves': score.winner_moves}

            if score.loser in performance:
                ranking = performance[score.loser]
                ranking['losses'] += 1
            else:
                performance[score.loser] = {
                    'name': score.get_loser_name(), 'wins': 0, 'losses': 1,
                    'avg_moves': 0}

        perf = sorted(performance.itervalues(),
                      key=lambda x: (-x['wins'], -x['avg_moves']))

        return RankingForms(
            items=[RankingForm(user_name=p['name'].get_result(),
                               rank=rank + 1,
                               performance=self._win_loss_ratio(p['wins'],
                                                                p['losses']))
                   for rank, p in
                   enumerate(perf)]
        )

    def _win_loss_ratio(self, wins, losses):
        return wins / (wins + losses)

# registers API
api = endpoints.api_server([TicTacToeApi])
