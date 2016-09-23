"""utils.py - File for collecting general utility functions."""

import endpoints
from google.appengine.ext import ndb
from google.appengine.api import mail, app_identity


def get_by_urlsafe(urlsafe, model):
    """Returns an ndb.Model entity that the urlsafe key points to. Checks
        that the type of entity returned is of the correct kind. Raises an
        error if the key String is malformed or the entity is of the incorrect
        kind
    Args:
        urlsafe: A urlsafe key string
        model: The expected entity kind
    Returns:
        The entity that the urlsafe Key string points to or None if no entity
        exists.
    Raises:
        ValueError:"""
    try:
        key = ndb.Key(urlsafe=urlsafe)
    except TypeError as e:
        raise endpoints.BadRequestException('Invalid Key')
    except Exception, e:
        if e.__class__.__name__ == 'ProtocolBufferDecodeError':
            raise endpoints.BadRequestException('Invalid Key')
        else:
            raise

    entity = key.get()
    if not entity:
        return None
    if not isinstance(entity, model):
        raise ValueError('Incorrect Kind')
    return entity


def send_turn_reminder_email(user, urlsafe_game_key):
    app_id = app_identity.get_application_id()
    subject = "It's your turn!"
    body = ("Hello {}, \n\nIt's your turn to play! Following is your "
            "game's key:\n\n{}".format(user.name, urlsafe_game_key))

    mail.send_mail('noreply@{}.appspotmail.com'.format(app_id),
                   user.email,
                   subject,
                   body)
