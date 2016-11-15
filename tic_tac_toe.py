# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

from __future__ import division

import endpoints
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.ext.db import TransactionFailedError

from models import (
    Game,
    GameForm,
    GameForms,
    MakeMoveForm,
    MoveHistoryForms,
    RankingForm,
    RankingForms,
    Score,
    ScoreForms,
    StringMessage,
    User,
    PlayersForm,
)
from protorpc import message_types, messages, remote

from utils import get_by_urlsafe


NEW_GAME_REQUEST = endpoints.ResourceContainer(PlayersForm)
JOIN_GAME_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1),
    urlsafe_game_key=messages.StringField(2),
)
URL_SAFE_KEY_CONTAINER = endpoints.ResourceContainer(
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

    def _get_game(self, urlsafe_game_key):
        """
        Retrieves a game by its URL safe key.
        Args:
            urlsafe_game_key: URL safe key for game to retrieve.

        Returns:
            Game instance.
        """
        game = get_by_urlsafe(urlsafe_game_key, Game)

        if not game:
            raise endpoints.NotFoundException('Game not found!')

        return game

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user/create',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Creates a User. Requires a unique username."""

        if User.query(ndb.OR(User.name == request.user_name,
                             User.email == request.email)).get():
            raise endpoints.ConflictException(
                    'A User with that name or email already exists!')

        user = User(name=request.user_name, email=request.email)
        user.put()

        return StringMessage(message='User {} created!'.format(
                request.user_name))

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/new',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """
        Creates a new game.
        Returns a GameForm describing the game.
        """
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
        except TransactionFailedError:
            raise endpoints.BadRequestException('Error saving Game.')

        return game.to_form('Good luck playing Tic Tac Toe!')

    @endpoints.method(request_message=JOIN_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}/join',
                      name='join_game',
                      http_method='PUT')
    def join_game(self, request):
        """
        Joins user to game as player2.
        Returns a GameForm describing the game.
        """
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        game = self._get_game(request.urlsafe_game_key)

        if user.key == game.player1:
            raise endpoints.ConflictException(
                'Player #2 cannot be the same as Player #1.')

        if game.player2:
            raise endpoints.ConflictException('Game is already full!')
        try:
            game.set_player2(user.key)
        except ValueError as err:
            raise endpoints.BadRequestException(err.message)

        return game.to_form("You've joined the game. Good luck playing "
                            "Tic Tac Toe!")

    @endpoints.method(request_message=URL_SAFE_KEY_CONTAINER,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = self._get_game(request.urlsafe_game_key)
        if game.game_over:
            return game.to_form('This game is alresdy over. Start a new game.')
        else:
            return game.to_form('Time to make a move!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}/move',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""

        game = self._get_game(request.urlsafe_game_key)

        if game.game_over:
            return game.to_form('Game already over.')

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
            raise endpoints.NotFoundException('Cell #{} does not exist.'
                                                .format(request.position))
        elif cell != -1:
            raise endpoints.ConflictException('Cell #{} is already occupied.'
                                                .format(request.position))

        game.set_position(request.position, user)
        game.next_turn = game.player2 if game.player1 == user.key else game.player1

        symbol = TicTacToeApi.check_for_win(game=game)
        if symbol > -1:
            game.end_game(winner=user.key)
            return game.to_form('You won!')
        elif TicTacToeApi.is_grid_full(game):
            game.end_game(winner=None)
            return game.to_form('It is a draw!')

        game.put()
        taskqueue.add(url='/tasks/notify_next_turn/{}/{}'
                      .format(request.urlsafe_game_key, game.next_turn.urlsafe()))
        return game.to_form()

    @staticmethod
    def check_for_win(game):
        """
        Determines if the game has been won by any one player.
        Args:
            game(Game): Game instance

        Returns:
            The symbol of the player who won, or -1 if no player has won.
        """
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

    @staticmethod
    def is_grid_full(game):

        grid = game.grid

        for i in range(3):
            for j in range(3):
                if grid[i][j] == -1:
                    return False

        return True

    @endpoints.method(request_message=message_types.VoidMessage,
                      response_message=ScoreForms,
                      path='scores',
                      http_method='GET')
    def get_scores(self, request):
        """Retrieves all user scores recorded in the database."""
        return ScoreForms(items=[score.to_form() for score in Score.query()])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='user/scores/{user_name}',
                      http_method='GET')
    def get_user_scores(self, request):
        """Retrieves all of an individual User's scores."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        scores = Score.query(ndb.OR(Score.winner == user.key,
                                    Score.loser == user.key))
        return ScoreForms(items=[score.to_form() for score in scores])

    @endpoints.method(request_message=GET_USER_GAMES_REQUEST,
                      response_message=GameForms,
                      path='user/games/{user_name}',
                      http_method='GET')
    def get_user_games(self, request):
        """Retrieves all games created by a user."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        games = Game.query(
            ndb.OR(Game.player1 == user.key,
                   Game.player2 == user.key)
        ).filter(Game.game_over == False).fetch()
        if games:
            return GameForms(items=[game.to_form() for game in games])
        else:
            raise endpoints.NotFoundException(
                'User {} has not created any games.'.format(request.user_name))

    @endpoints.method(request_message=URL_SAFE_KEY_CONTAINER,
                      response_message=StringMessage,
                      path='game/{urlsafe_game_key}/cancel',
                      http_method='PUT')
    def cancel_game(self, request):
        """Cancels the given game."""
        game = self._get_game(request.urlsafe_game_key)

        if game.game_over:
            raise endpoints.BadRequestException(
                'Game cannot be cancelled because it is already over.')
        else:
            game.cancelled = True
            game.game_over = True
            game.put()

            return StringMessage(message='Game cancelled.')

    @endpoints.method(request_message=message_types.VoidMessage,
                      response_message=RankingForms,
                      path='user/rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Computes and returns all user rankings."""
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
                    'name_future': score.get_winner_name_future(),
                    'wins': 1, 'losses': 0,
                    'avg_moves': score.winner_moves}

            if score.loser in performance:
                ranking = performance[score.loser]
                ranking['losses'] += 1
            else:
                performance[score.loser] = {
                    'name_future': score.get_loser_name_future(),
                    'wins': 0, 'losses': 1,
                    'avg_moves': 0}

        performance = sorted(performance.itervalues(),
                             key=lambda x: (-x['wins'], x['avg_moves']))

        return RankingForms(
            items=[RankingForm(user_name=p['name_future'].get_result(),
                               rank=rank + 1,
                               performance=self._win_loss_ratio(p['wins'],
                                                                p['losses']))
                   for rank, p in
                   enumerate(performance)]
        )

    def _win_loss_ratio(self, wins, losses):
        return wins / float(wins + losses)

    @endpoints.method(request_message=URL_SAFE_KEY_CONTAINER,
                      response_message=MoveHistoryForms,
                      path='game/{urlsafe_game_key}/history',
                      http_method='GET')
    def get_game_history(self, request):
        """Retrieves the play-by-play history for the given Game."""
        game = self._get_game(request.urlsafe_game_key)
        return game.get_history_forms()


# registers API
api = endpoints.api_server([TicTacToeApi])
