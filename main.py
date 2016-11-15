#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""
import webapp2
import datetime
from utils import get_by_urlsafe, send_turn_reminder_email

from models import User, Game


class SendReminderEmail(webapp2.RequestHandler):
    def get(self):
        """
        Send a reminder email to each User who has a pending for more than 12
        hours. Called every hour using a cron job.
        """
        users = User.query(User.email != None)
        date = datetime.datetime.now()
        query = Game.query(Game.last_move <= date - datetime.timedelta(minutes=12))
        user_game = {game.next_turn: game
                     for game in query}

        for user in users:
            if user.key in user_game.keys():
                send_turn_reminder_email(user, user_game[user.key].key.urlsafe())


class SendNotificationNextPlayer(webapp2.RequestHandler):
    def post(self, urlsafe_game_key, urlsafe_user_key):
        """Send a notification to player to play next."""

        user = get_by_urlsafe(urlsafe_user_key, User)

        if user:
            send_turn_reminder_email(user, urlsafe_game_key)


app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail),
    ('/tasks/notify_next_turn/(\w+)/(\w+)', SendNotificationNextPlayer),
], debug=True)
