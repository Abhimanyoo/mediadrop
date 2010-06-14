# This file is a part of MediaCore, Copyright 2009 Simple Station Inc.
#
# MediaCore is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MediaCore is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Podcast Models

SQLAlchemy ORM definitions for:

* :class:`Podcast`

.. moduleauthor:: Nathan Wright <nathan@simplestation.com>

"""
from datetime import datetime
from sqlalchemy import Table, ForeignKey, Column, sql
from sqlalchemy.types import String, Unicode, UnicodeText, Integer, DateTime, Boolean, Float
from sqlalchemy.orm import mapper, relation, backref, synonym, composite, validates, dynamic_loader, column_property
from pylons import request

from mediacore.model import Author, slug_length, slugify, get_available_slug
from mediacore.model.meta import DBSession, metadata
from mediacore.model.media import Media, MediaQuery, media


podcasts = Table('podcasts', metadata,
    Column('id', Integer, autoincrement=True, primary_key=True),
    Column('slug', String(slug_length), unique=True, nullable=False),
    Column('created_on', DateTime, default=datetime.now, nullable=False),
    Column('modified_on', DateTime, default=datetime.now, onupdate=datetime.now, nullable=False),
    Column('title', Unicode(50), nullable=False),
    Column('subtitle', Unicode(255)),
    Column('description', UnicodeText),
    Column('category', Unicode(50)),
    Column('author_name', Unicode(50), nullable=False),
    Column('author_email', Unicode(50), nullable=False),
    Column('explicit', Boolean, default=None),
    Column('copyright', Unicode(50)),
    Column('itunes_url', String(80)),
    Column('feedburner_url', String(80)),
    mysql_engine='InnoDB',
    mysql_charset='utf8',
)


class Podcast(object):
    """
    Podcast Metadata

    .. attribute:: id
    .. attribute:: slug

        A unique URL-friendly permalink string for looking up this object.

    .. attribute:: created_on
    .. attribute:: modified_on

    .. attribute:: title
    .. attribute:: subtitle
    .. attribute:: description

    .. attribute:: category

        The `iTunes category <http://www.apple.com/itunes/podcasts/specs.html#categories>`_

        Values with a ``>`` are parsed with special meaning. ``Arts > Design``
        implies that this pertains to the Design subcategory of Arts, and the
        feed markup reflects that.

    .. attribute:: author

        An instance of :class:`mediacore.model.authors.Author`.
        Although not actually a relation, it is implemented as if it were.
        This was decision was made to make it easier to integrate with
        :class:`mediacore.model.auth.User` down the road.

    .. attribute:: explicit

        The `iTunes explicit <http://www.apple.com/itunes/podcasts/specs.html#explicit>`_
        value.

            * ``True`` means 'yes'
            * ``None`` means no advisory displays, ie. 'no'
            * ``False`` means 'clean'

    .. attribute:: copyright

    .. attribute:: itunes_url

        Optional iTunes subscribe URL.

    .. attribute:: feedburner_url

        Optional Feedburner URL. If set, requests for this podcast's feed will
        be forwarded to this address -- unless, of course, the request is
        coming from Feedburner.

    .. attribute:: media

        A dynamic loader for :class:`mediacore.model.media.Media` episodes:
        see :class:`mediacore.model.media.MediaQuery`.

    .. attribute:: media_count

        The number of :class:`mediacore.model.media.Media` episodes.

    .. attribute:: media_count_published

        The number of :class:`mediacore.model.media.Media` episodes that are
        currently published.

    """

    query = DBSession.query_property()

    _thumb_dir = 'podcasts'

    def __repr__(self):
        return '<Podcast: %s>' % self.slug

    @validates('slug')
    def validate_slug(self, key, slug):
        return slugify(slug)


mapper(Podcast, podcasts, properties={
    'author': composite(Author,
        podcasts.c.author_name,
        podcasts.c.author_email),
    'media': dynamic_loader(Media, backref='podcast', query_class=MediaQuery, passive_deletes=True),
    'media_count':
        column_property(
            sql.select(
                [sql.func.count(media.c.id)],
                media.c.podcast_id == podcasts.c.id,
            ).label('media_count'),
            deferred=True
        ),
    'media_count_published':
        column_property(
            sql.select(
                [sql.func.count(media.c.id)],
                sql.and_(
                    media.c.podcast_id == podcasts.c.id,
                    media.c.reviewed == True,
                    media.c.encoded == True,
                    media.c.publishable == True,
                    media.c.publish_on <= datetime.now(),
                    sql.or_(
                        media.c.publish_until == None,
                        media.c.publish_until >= datetime.now()
                    ),
                )
            ).label('media_count_published'),
            deferred=True
        )
})


def create_podcast_stub():
    """Return a new :class:`Podcast` instance with helpful defaults.

    This is used any time we need a placeholder db record, such as when:

        * Some admin uploads a thumbnail *before* saving their new media

    """
    user = request.environ['repoze.who.identity']['user']
    timestamp = datetime.now().strftime('%b-%d-%Y')
    podcast = Podcast()
    podcast.slug = get_available_slug(Podcast, 'stub-%s' % timestamp)
    podcast.title = '(Stub %s created by %s)' % (timestamp, user.display_name)
    podcast.author = Author(user.display_name, user.email_address)
    return podcast
