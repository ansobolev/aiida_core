from aiida.restapi.common.utils import parse_query_string,\
    parse_path, paginate, validate_request, build_response, build_headers
from urllib import unquote

from flask import request
from flask_restful import Resource

from aiida.backends.utils import load_dbenv, is_dbenv_loaded
if not is_dbenv_loaded():
    load_dbenv()

## TODO add the caching support. I cache total count, results, and possibly
# set_query
class BaseResource(Resource):
    ## Each derived class will instantiate a different type of translator.
    # This is the only difference in the classes.
    def __init__(self):
        self.trans = None

    def get(self, **kwargs):
        """
        Get method for the Computer resource
        :return:
        """

        ## Decode url parts
        path = unquote(request.path)
        query_string = unquote(request.query_string)
        url = unquote(request.url)
        url_root = unquote(request.url_root)

        ## Parse request
        (resource_type, page, pk, query_type) = parse_path(path)

        ## schema request (static)
        if query_type == "schema":
            headers = build_headers(url=request.url, total_count=0)
            results = self.trans.get_schema()
        else:
            (limit, offset, perpage, orderby, filters, alist, nalist, elist,
             nelist) = parse_query_string(query_string)

            ## Validate request
            validate_request(limit=limit, offset=offset, perpage=perpage, page=page)

            ## Set the query, and initialize qb object
            self.trans.set_query(filters=filters, orders=orderby, pk=pk)

            ## Count results
            total_count = self.trans.get_total_count()

            ## Pagination (if required)
            if page is not None:
                (limit, offset, rel_pages) = paginate(page, perpage, total_count)
                self.trans.set_limit_offset(limit=limit, offset=offset)
                headers = build_headers(rel_pages=rel_pages, url=request.url,
                                        total_count=total_count)
            else:
                self.trans.set_limit_offset(limit=limit, offset=offset)
                headers = build_headers(url=request.url, total_count=total_count)

            ## Retrieve results
            results = self.trans.get_results()

        ## Build response
        data = dict(method=request.method,
                    url=url,
                    url_root=url_root,
                    path=request.path,
                    pk=pk,
                    query_string=request.query_string,
                    resource_type=resource_type,
                    data=results)
        return build_response(status=200, headers=headers, data=data)


class Node(Resource):
    ##Differs from BaseResource in trans.set_query() mostly because it takes
    # query_type as an input
    def __init__(self):
        from aiida.restapi.translator.node import NodeTranslator
        self.trans = NodeTranslator()
        from aiida.orm import Node
        self.tclass = Node

    def get(self, **kwargs):
        """
        Get method for the Calculation resource
        :return:
        """

        ## Decode url parts
        path = unquote(request.path)
        query_string = unquote(request.query_string)
        url = unquote(request.url)
        url_root = unquote(request.url_root)

        ## Parse request
        (resource_type, page, pk, query_type) = parse_path(path)

        ## schema request (static)
        if query_type == "schema":
            headers = build_headers(url=request.url, total_count=0)
            results = self.trans.get_schema()
        elif query_type == "statistics":
            headers = build_headers(url=request.url, total_count=0)
            results = self.trans.get_statistics(self.tclass)
        else:
            (limit, offset, perpage, orderby, filters, alist, nalist, elist,
             nelist) = parse_query_string(query_string)

            ## Validate request
            validate_request(limit=limit, offset=offset, perpage=perpage, page=page)

            ## Instantiate a translator and initialize it
            self.trans.set_query(filters=filters, orders=orderby,
                              query_type=query_type, pk=pk, alist=alist,
                                 nalist=nalist, elist=elist, nelist=nelist)

            ## Count results
            total_count = self.trans.get_total_count()

            ## Pagination (if required)
            if page is not None:
                (limit, offset, rel_pages) = paginate(page, perpage, total_count)
                self.trans.set_limit_offset(limit=limit, offset=offset)
                headers = build_headers(rel_pages=rel_pages, url=request.url,
                                        total_count=total_count)
            else:
                self.trans.set_limit_offset(limit=limit, offset=offset)
                headers = build_headers(url=request.url, total_count=total_count)

            ## Retrieve results
            results = self.trans.get_results()

        ## Build response
        data = dict(method=request.method,
                    url=url,
                    url_root=url_root,
                    path=path,
                    pk=pk,
                    query_string=query_string,
                    resource_type=resource_type,
                    data=results)
        return build_response(status=200, headers=headers, data=data)

class Computer(BaseResource):
    def __init__(self):
        ## Instantiate the correspondent translator
        from aiida.restapi.translator.computer import ComputerTranslator
        self.trans = ComputerTranslator()

class Group(BaseResource):
    def __init__(self):
        from aiida.restapi.translator.group import GroupTranslator
        self.trans = GroupTranslator()

class User(BaseResource):
    def __init__(self):
        from aiida.restapi.translator.user import UserTranslator
        self.trans = UserTranslator()

class Calculation(Node):
    def __init__(self):
        from aiida.restapi.translator.calculation import CalculationTranslator
        self.trans = CalculationTranslator()
        from aiida.orm import Calculation
        self.tclass = Calculation

class Code(Node):
    def __init__(self):
        from aiida.restapi.translator.code import CodeTranslator
        self.trans = CodeTranslator()
        from aiida.orm import Code
        self.tclass = Code

class Data(Node):
    def __init__(self):
        from aiida.restapi.translator.data import DataTranslator
        self.trans = DataTranslator()
        from aiida.orm import Data
        self.tclass = Data
