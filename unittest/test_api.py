import unittest
from api import TicTacToeApi
import mock


class TestTicTacToeApi(unittest.BaseTestSuite):

    def test__check_for_win(self):
        game = mock.Mock()
        game.grid = [[1, -1, 1], [1, 0, 0], [-1, -1, -1]]
        winner = TicTacToeApi.check_for_win(game=game)

