###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for :mod:`aiida.storage.utils`."""

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from aiida.storage.utils import _create_smarter_in_clause


@pytest.fixture
def sqlite_session():
    """In-memory SQLite session with a small integer-ID table (IDs 1-5)."""
    engine = sa.create_engine('sqlite://')
    metadata = sa.MetaData()
    table = sa.Table('items', metadata, sa.Column('id', sa.Integer, primary_key=True))
    metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(sa.insert(table).values([{'id': i} for i in range(1, 6)]))
        session.commit()
        yield session, table.c.id


@pytest.fixture
def sqlite_million_rows():
    """In-memory SQLite session with 1M rows (IDs 1-1,000,000), inserted via bulk SQL."""
    engine = sa.create_engine('sqlite://')
    metadata = sa.MetaData()
    table = sa.Table('items', metadata, sa.Column('id', sa.Integer, primary_key=True))
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.insert(table), [{'id': i} for i in range(1, 1_000_001)])
    with Session(engine) as session:
        yield session, table.c.id


def test_smarter_in_clause_sqlite_small_list(sqlite_session):
    """``_create_smarter_in_clause`` returns exactly the matching rows on SQLite (small list)."""
    session, column = sqlite_session
    result = (
        session.execute(
            sa.select(column).where(_create_smarter_in_clause(session=session, column=column, values=[2, 4]))
        )
        .scalars()
        .all()
    )
    assert sorted(result) == [2, 4]


@pytest.mark.requires_psql
@pytest.mark.nightly
@pytest.mark.usefixtures('aiida_profile_clean')
def test_smarter_in_clause_psql_small_list():
    """``_create_smarter_in_clause`` returns exactly the matching rows on PostgreSQL (small list)."""
    from aiida.manage import get_manager
    from aiida.storage.psql_dos.models.node import DbNode
    from tests.utils.nodes import create_int_nodes

    storage = get_manager().get_profile_storage()
    session = storage.get_session()
    node_pks = create_int_nodes(5)
    returned_pks = sorted(
        session.execute(
            sa.select(DbNode.id).where(_create_smarter_in_clause(session=session, column=DbNode.id, values=node_pks))
        )
        .scalars()
        .all()
    )
    assert returned_pks == sorted(node_pks)


@pytest.mark.nightly
def test_smarter_in_clause_sqlite_real_world(sqlite_million_rows):
    """Real-world scenario on SQLite: 1M rows, >500k query list returns the correct results.

    Uses all odd IDs from 1 to 1,000,001 (500,001 items), exceeding the 500k batching
    threshold, against a table containing IDs 1-1,000,000. The 500,000 matching odd IDs
    (1, 3, ..., 999,999) should be returned; 1,000,001 is not in the table.
    """
    session, column = sqlite_million_rows
    query_ids = list(range(1, 1_000_002, 2))  # 500,001 odd IDs — triggers batching
    count, min_id, max_id = session.execute(
        sa.select(
            sa.func.count(column),
            sa.func.min(column),
            sa.func.max(column),
        ).where(_create_smarter_in_clause(session=session, column=column, values=query_ids))
    ).one()
    assert count == 500_000
    assert min_id == 1
    assert max_id == 999_999


@pytest.mark.requires_psql
@pytest.mark.nightly
@pytest.mark.usefixtures('aiida_profile_clean')
def test_smarter_in_clause_psql_real_world():
    """Real-world scenario on PostgreSQL: 1M rows, >500k query list returns the correct results.

    Inserts 1M rows into a temporary table via ``generate_series`` (no Python loop, no AiiDA ORM),
    then queries with all odd IDs from 1 to 1,000,001 (500,001 items). The 500,000 matching
    odd IDs (1, 3, ..., 999,999) should be returned; 1,000,001 is not in the table.
    """
    from aiida.manage import get_manager

    storage = get_manager().get_profile_storage()
    session = storage.get_session()

    if session.bind.dialect.name != 'postgresql':
        pytest.skip('This test requires a PostgreSQL profile')

    session.execute(sa.text('CREATE TEMP TABLE test_items (id INTEGER PRIMARY KEY)'))
    session.execute(sa.text('INSERT INTO test_items SELECT generate_series(1, 1000000)'))

    column = sa.Table('test_items', sa.MetaData(), sa.Column('id', sa.Integer)).c.id
    query_ids = list(range(1, 1_000_002, 2))  # 500,001 odd IDs — triggers batching
    count, min_id, max_id = session.execute(
        sa.select(
            sa.func.count(column),
            sa.func.min(column),
            sa.func.max(column),
        ).where(_create_smarter_in_clause(session=session, column=column, values=query_ids))
    ).one()
    assert count == 500_000
    assert min_id == 1
    assert max_id == 999_999
