"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

from datetime import date, datetime
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()


class MoveHistory(ndb.Model):
    """Structured game move history consisting of user and position."""
    user_name = ndb.StringProperty()
    position = ndb.IntegerProperty()

    def to_form(self):
        return MoveHistoryForm(player=self.user_name, position=self.position)


class Game(ndb.Model):
    """Tic Tac Toe Game object

    The grid is represented by individual cells, numbered as follows:

     1 | 2 | 3
    -----------
     4 | 5 | 6
    -----------
     7 | 8 | 9

     by fields cell_1 .. cell_9.

     Each cell can have the possible values of -1 (empty),
     0 (O), or 1 (X).

     player1 is automatically assigned 'X', player2 is 'O'.
    """

    game_over = ndb.BooleanProperty(required=True, default=False)
    player1 = ndb.KeyProperty(required=True, kind='User')
    player2 = ndb.KeyProperty(required=False, kind='User')
    next_turn = ndb.KeyProperty(required=True, kind='User')
    winner = ndb.KeyProperty(required=False, kind='User')
    last_move = ndb.DateTimeProperty(required=False)
    cancelled = ndb.BooleanProperty(required=False, default=False)
    cell_1 = ndb.IntegerProperty(required=False, default=-1)
    cell_2 = ndb.IntegerProperty(required=False, default=-1)
    cell_3 = ndb.IntegerProperty(required=False, default=-1)
    cell_4 = ndb.IntegerProperty(required=False, default=-1)
    cell_5 = ndb.IntegerProperty(required=False, default=-1)
    cell_6 = ndb.IntegerProperty(required=False, default=-1)
    cell_7 = ndb.IntegerProperty(required=False, default=-1)
    cell_8 = ndb.IntegerProperty(required=False, default=-1)
    cell_9 = ndb.IntegerProperty(required=False, default=-1)
    history = ndb.LocalStructuredProperty(MoveHistory, repeated=True)

    @property
    def grid(self):
        """Returns the game grid represented as a list of lists"""
        l = [[], [], []]
        i = 1
        for j in range(3):
            for k in range(3):
                l[j].append(getattr(self, 'cell_{}'.format(i)))
                i += 1
        return l

    @grid.setter
    def grid(self, grid_list):
        """Store game grid in database"""
        i = 1
        for j in range(3):
            for k in range(3):
                setattr(self, 'cell_{}'.format(i), grid_list[j][k])
                i += 1

    @staticmethod
    def _cell_names():
        for i in range(1, 10):
            attr_name = 'cell_{}'.format(i)
            yield attr_name

    def _record_move_history(self, user, position):
        move = MoveHistory(user_name=user.name, position=position)
        self.history.append(move)

    def get_player_symbol(self, user_key):
        if self.player1 == user_key:
            return 1
        elif self.player2 == user_key:
            return 0
        else:
            raise ValueError('User not in this game.')

    @classmethod
    def new_game(cls, player1_key, player2_key=None):
        """Creates and returns a new game"""

        game = Game(player1=player1_key,
                    player2=player2_key,
                    next_turn=player1_key,
                    game_over=False)
        game.put()
        return game

    def set_player2(self, user_key):
        self.player2 = user_key
        self.put()

    def set_position(self, position, user):
        symbol = self.get_player_symbol(user.key)
        attr_name = 'cell_{}'.format(position)
        setattr(self, attr_name, symbol)
        self.last_move = datetime.now()
        self._record_move_history(user, position)

    def cancel_game(self):
        self.cancelled = True

    def get_number_of_moves(self, user_key):
        symbol = self.get_player_symbol(user_key)
        total = 0
        for attr_name in self._cell_names():
            if getattr(self, attr_name) == symbol:
                total += 1
        return total

    def to_form(self, message=''):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.player1_name = self.player1.get().name
        form.player2_name = self.player2.get().name if self.player2 else None
        form.game_over = self.game_over
        form.message = message
        form.next_turn = self.next_turn.get().name

        for attr_name in self._cell_names():
            setattr(form, attr_name, getattr(self, attr_name))

        return form

    def get_history_forms(self):
        return MoveHistoryForms(items=[event.to_form() for event in self.history])

    def end_game(self, winner):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        futures = []
        self.game_over = True
        self.winner = winner
        futures.append(self.put_async())

        if not winner:
            loser = None
        else:
            loser = self.player2 if winner == self.player1 else self.player1

        # Add the game to the 'score board'
        score = Score(parent=self.key, date=date.today(),
                      winner=winner, winner_name=winner.get().name,
                      loser=loser, loser_name=loser.get().name,
                      winner_moves=self.get_number_of_moves(winner))
        futures.append(score.put_async())
        ndb.Future.wait_all(futures)


class Score(ndb.Model):
    """Score object"""
    winner = ndb.KeyProperty(required=True, kind='User')
    winner_name = ndb.StringProperty(required=True)
    loser = ndb.KeyProperty(required=True, kind='User')
    loser_name = ndb.StringProperty(required=True)
    date = ndb.DateProperty(required=True)
    winner_moves = ndb.IntegerProperty(required=True)

    @ndb.tasklet
    def get_winner_name_future(self):
        user = yield self.winner.get_async()
        raise ndb.Return(user.name)

    @ndb.tasklet
    def get_loser_name_future(self):
        user = yield self.loser.get_async()
        raise ndb.Return(user.name)

    @classmethod
    def query_user(cls, user_key):
        return cls.query(ndb.OR(cls.winner == user_key,
                                cls.loser == user_key))

    def to_form(self):
        return ScoreForm(winner=self.winner_name,
                         date=str(self.date),
                         moves=self.winner_moves)


class MoveHistoryForm(messages.Message):
    """Form for game history information"""
    player = messages.StringField(1, required=True)
    position = messages.IntegerField(2, required=True)


class MoveHistoryForms(messages.Message):
    """Form for game history information"""
    items = messages.MessageField(MoveHistoryForm, 1, repeated=True)


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    game_over = messages.BooleanField(2, required=True)
    message = messages.StringField(3, required=True)
    player1_name = messages.StringField(4, required=True)
    player2_name = messages.StringField(5, required=False)
    next_turn = messages.StringField(6, required=True)
    cell_1 = messages.IntegerField(7, required=True)
    cell_2 = messages.IntegerField(8, required=True)
    cell_3 = messages.IntegerField(9, required=True)
    cell_4 = messages.IntegerField(10, required=True)
    cell_5 = messages.IntegerField(11, required=True)
    cell_6 = messages.IntegerField(12, required=True)
    cell_7 = messages.IntegerField(13, required=True)
    cell_8 = messages.IntegerField(14, required=True)
    cell_9 = messages.IntegerField(15, required=True)


class GameForms(messages.Message):
    """Return multiple GameForm """
    items = messages.MessageField(GameForm, 1, repeated=True)


class PlayersForm(messages.Message):
    """User name"""
    player_1 = messages.StringField(1, required=True)
    player_2 = messages.StringField(2, required=False)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    user_name = messages.StringField(1, required=True)
    position = messages.IntegerField(2, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    winner = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    moves = messages.IntegerField(3, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForm"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class RankingForm(messages.Message):
    """Outbound ranking information"""
    user_name = messages.StringField(1, required=True)
    rank = messages.IntegerField(2, required=True)
    performance = messages.FloatField(3, required=True)


class RankingForms(messages.Message):
    """Return multiple RankingForm"""
    items = messages.MessageField(RankingForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)

