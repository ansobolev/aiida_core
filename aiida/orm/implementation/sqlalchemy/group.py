# -*- coding: utf-8 -*-

import collections

from copy import copy


from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.session import make_transient


from aiida.backends import sqlalchemy as sa
from aiida.backends.sqlalchemy.models.group import DbGroup, table_groups_nodes
from aiida.backends.sqlalchemy.models.node import DbNode
from aiida.backends.utils import get_automatic_user

from aiida.common.exceptions import (ModificationNotAllowed, UniquenessError)

from aiida.orm.implementation.general.group import AbstractGroup


class Group(AbstractGroup):

    def __init__(self, **kwargs):
        dbgroup = kwargs.pop('dbgroup', None)

        if dbgroup is not None:
            if isinstance(dbgroup, (int, long)):
                dbgroup = DbGroup.query.filter_by(id=dbgroup).first()
                if not dbgroup:
                    raise NotExistent("Group with pk={} does not exist".format(
                        dbgroup))

            if not isinstance(dbgroup, DbGroup):
                raise TypeError("dbgroup is not a DbGroup instance, it is "
                                "instead {}".format(str(type(dbgroup))))
            if kwargs:
                raise ValueError("If you pass a dbgroups, you cannot pass any "
                                 "further parameter")

            self._dbgroup = dbgroup
        else:
            name = kwargs.pop('name', None)
            if name is None:
                raise ValueError("You have to specify a group name")
            group_type = kwargs.pop('type_string', "")  # By default, an user group
            user = kwargs.pop('user', get_automatic_user())
            description = kwargs.pop('description', "")

            if kwargs:
                raise ValueError("Too many parameters passed to Group, the "
                                 "unknown parameters are: {}".format(
                                     ", ".join(kwargs.keys())))

            self._dbgroup = DbGroup(name=name, description=description,
                                    user=user, type=group_type)

    @property
    def name(self):
        return self.dbgroup.name

    @property
    def description(self):
        return self.dbgroup.description

    @description.setter
    def description(self, value):
        self.dbgroup.description = value

        # Update the entry in the DB, if the group is already stored
        if self._is_stored:
            self.dbgroup.save()


    @property
    def type_string(self):
        return self.dbgroup.type

    @property
    def user(self):
        return self.dbgroup.user

    @property
    def dbgroup(self):
        return self._dbgroup

    @property
    def pk(self):
        return self.dbgroup.id

    @property
    def uuid(self):
        return unicode(self.dbgroup.uuid)

    def __int__(self):
        if self._to_be_stored:
            return None
        else:
            return self._dbnode.id

    @property
    def _is_stored(self):
        return self.pk is not None

    def store(self):
        if self._is_stored:
            raise ModificationNotAllowed("Cannot restore a group that was "
                                         "already stored")
        else:
            try:
                self.dbgroup.save()
            except SQLAlchemyError:
                raise UniquenessError("A group with the same name (and of the "
                                      "same type) already "
                                      "exists, unable to store")

        return self

    def add_nodes(self, nodes):
        if not self._is_stored:
            raise ModificationNotAllowed("Cannot add nodes to a group before "
                                         "storing")
        from aiida.orm.implementation.sqlalchemy.node import Node

        # First convert to a list
        if isinstance(nodes, (Node, DbNode)):
            nodes = [nodes]

        if isinstance(nodes, basestring) or not isinstance(
                nodes, collections.Iterable):
            raise TypeError("Invalid type passed as the 'nodes' parameter to "
                            "add_nodes, can only be a Node, DbNode, or a list "
                            "of such objects, it is instead {}".format(
                                str(type(nodes))))

        list_nodes = []
        for node in nodes:
            if not isinstance(node, (Node, DbNode)):
                raise TypeError("Invalid type of one of the elements passed "
                                "to add_nodes, it should be either a Node or "
                                "a DbNode, it is instead {}".format(
                                    str(type(node))))
            if node.id is None:
                raise ValueError("At least one of the provided nodes is "
                                 "unstored, stopping...")
            if isinstance(node, Node):
                list_nodes.append(node.dbnode)
            else:
                list_nodes.append(node)

        self.dbgroup.dbnodes.extend(list_nodes)

    @property
    def nodes(self):
        class iterator(object):
            def __init__(self, dbnodes):
                self.dbnodes = dbnodes
                self.generator = self._genfunction()

            def _genfunction(self):
                for n in self.dbnodes:
                    yield n.get_aiida_class()

            def __iter__(self):
                return self

            def __len__(self):
                return len(self.dbnodes)

            # For future python-3 compatibility
            def __next__(self):
                return self.next()

            def next(self):
                return next(self.generator)

        return iterator(self.dbgroup.dbnodes.all())

    def remove_nodes(self, nodes):
        if not self._is_stored:
            raise ModificationNotAllowed("Cannot remove nodes from a group "
                                         "before storing")

        from aiida.orm.implementation.sqlalchemy.node import Node
        # First convert to a list
        if isinstance(nodes, (Node, DbNode)):
            nodes = [nodes]

        if isinstance(nodes, basestring) or not isinstance(
                nodes, collections.Iterable):
            raise TypeError("Invalid type passed as the 'nodes' parameter to "
                            "remove_nodes, can only be a Node, DbNode, or a "
                            "list of such objects, it is instead {}".format(
                                str(type(nodes))))

        list_nodes = []
        for node in nodes:
            if not isinstance(node, (Node, DbNode)):
                raise TypeError("Invalid type of one of the elements passed "
                                "to add_nodes, it should be either a Node or "
                                "a DbNode, it is instead {}".format(
                                    str(type(node))))
            if node.id is None:
                raise ValueError("At least one of the provided nodes is "
                                 "unstored, stopping...")
            if isinstance(node, Node):
                node = node.dbnode
            # If we don't check first, SqlA might issue a DELETE statement for
            # an unexisting key, resulting in an error
            if node in self.dbgroup.dbnodes:
                list_nodes.append(node)

        list(map(self.dbgroup.dbnodes.remove, list_nodes))


    @classmethod
    def query(cls, name=None, type_string="", pk = None, uuid=None, nodes=None,
              user=None, node_attributes=None, past_days=None, **kwargs):
        from aiida.orm.implementation.sqlalchemy.node import Node

        filters = []

        if name:
            filters.append(DbGroup.name == name)
        if type_string:
            filters.append(DbGroup.type == type_string)
        if pk:
            filters.append(DbGroup.id == pk)
        if uuid:
            filters.append(DbGroup.uuid == uuid)
        if past_days:
            filters.append(DbGroup.time >= past_days)
        if nodes:
            if not isinstance(nodes, collections.Iterable):
                nodes = [nodes]

            if not all(map(lambda n: isinstance(n, (Node, DbNode)), nodes)):
                raise TypeError("At least one of the elements passed as "
                                "nodes for the query on Group is neither "
                                "a Node nor a DbNode")


            # In the case of the Node orm from Sqlalchemy, there is an id
            # property on it.
            sub_query = (sa.session.query(table_groups_nodes).filter(
                table_groups_nodes.c["dbnode_id"].in_(map(lambda n: n.id, nodes)),
                table_groups_nodes.c["dbgroup_id"] == DbGroup.id
            ).exists())

            filters.append(sub_query)
        if user:
            if isinstance(user, basestring):
                filters.append(DbGroup.user.has(email = user))
            else:
                # This should be a DbUser
                filters.append(DbGroup.user == user)

        if node_attributes:
            # TODO SP: IMPLEMENT THIS
            pass

        # TODO SP: handle **kwargs
        groups = (sa.session.query(DbGroup.id).filter(*filters)
                  .order_by(DbGroup.id).distinct().all())

        return [cls(dbgroup=g[0]) for g in groups]


    def delete(self):
        if self.pk is not None:
            sa.session.delete(self._dbgroup)
            sa.session.commit()

            new_group = copy(self._dbgroup)
            make_transient(new_group)
            new_group.id = None
            self._dbgroup = new_group