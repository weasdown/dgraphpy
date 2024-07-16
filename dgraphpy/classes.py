from __future__ import annotations

import requests
import json


class Endpoint:
    headers: dict = {
        "Content-Type": "application/graphql",
    }

    def __init__(self, url: str):
        self.url: str = url

    def post(self, operation: GraphQLOperation):
        response = requests.post(url=self.url, data=operation.text, headers=Endpoint.headers)
        return response.json()
        # TODO remove
        # if isinstance(query_or_mutation, Query):
        #     return self.send_query(query_or_mutation)
        # elif isinstance(query_or_mutation, Mutation):
        #     return self.send_mutation(query_or_mutation)
        # else:
        #     raise AttributeError(f'query_or_mutation must be a Query or Mutation - was a {type(query_or_mutation)}')

    # TODO remove
    # def send_query(self, query: Query) -> dict:
    #     """
    #     Run a given query.
    #
    #     :param query:
    #     :type query:
    #     :return: JSON response from endpoint server.
    #     :rtype: dict
    #     """
    #     response = requests.post(url=self.url, data=query.text, headers=Endpoint.headers)
    #     return response.json()
    #
    # def send_mutation(self, mutation: Mutation) -> dict:
    #     """
    #     Run a given mutation.
    #
    #     :param mutation:
    #     :type mutation:
    #     :return: JSON response from endpoint server.
    #     :rtype: dict
    #     """
    #     response = requests.post(url=self.url, data=mutation.mutation_text, headers=Endpoint.headers)
    #     return response.json()


class GraphQLOperation:
    def __init__(self, gql_type: str, name: str, return_fields: list, arguments: dict = None):
        """
        Class for GraphQL queries. See https://graphql.org/learn/queries/
        """
        self.name: str = name
        self.gql_type: str = gql_type
        self.arguments = ''

        def parse_arguments(args: dict) -> str:
            """
            Convert an arguments dictionary into a GraphQL-compatible string.

            :param args: arguments dictionary
            :type args: dict
            :return: GraphQL-compatible string
            :rtype: str
            """

            gql_args = []

            for k, v in args.items():
                if isinstance(v, str):
                    item = str(k) + f': "{str(v)}"'
                elif isinstance(v, dict):
                    v_text = parse_arguments(v)
                    item = str(k) + ': {' + v_text + '}'
                elif isinstance(v, list):
                    item = f'{k}: {", ".join(v)}'
                else:
                    raise TypeError
                gql_args.append(item)
            return ', '.join(gql_args)

        if arguments is not None:
            self.arguments = parse_arguments(arguments)

            if self.name.startswith('query'):
                self.arguments = 'filter: {' + self.arguments + '}'

            self.arguments = '(' + self.arguments + ')'

        self.return_fields: list = return_fields

        self.return_fields_text: str = '{' + ",\n".join(return_fields) + '}'
        self.text: str = (f'{{{self.name}{self.arguments} '
                          f'{self.return_fields_text}}}')

    def post(self, endpoint: Endpoint = Endpoint('localhost:9080')) -> dict:
        """
        Send this query or mutation to a given endpoint via HTTP POST.

        :param endpoint: URL for endpoint. For standalone, use default ('localhost:9080')
        :type endpoint: str
        :return: JSON response from endpoint server.
        :rtype: dict
        """
        # response = requests.post(url=endpoint, data=self.query_text, headers=Endpoint.headers)
        # return response.json()
        return endpoint.post(self)


class Query(GraphQLOperation):
    def __init__(self, query_name: str, return_fields: list, arguments: dict = None):
        """
        Class for GraphQL queries. See https://graphql.org/learn/queries/
        """
        valid_start_words: list[str] = ['aggregate', 'get', 'query']
        if not any([query_name.startswith(start) for start in valid_start_words]):
            raise AttributeError(f'Query name must start with one of the following: {valid_start_words}')
        else:
            super().__init__('query', query_name, return_fields, arguments)
        # self.query_name: str = query_name
        # self.arguments = ''
        #
        # def parse_arguments(args: dict) -> str:
        #     """
        #     Convert an arguments dictionary into a GraphQL-compatible string.
        #
        #     :param args: arguments dictionary
        #     :type args: dict
        #     :return: GraphQL-compatible string
        #     :rtype: str
        #     """
        #
        #     gql_args = []
        #
        #     for k, v in args.items():
        #         if isinstance(v, str):
        #             item = str(k) + f': "{str(v)}"'
        #         elif isinstance(v, dict):
        #             v_text = parse_arguments(v)
        #             item = str(k) + ': {' + v_text + '}'
        #         elif isinstance(v, list):
        #             item = f'{k}: {", ".join(v)}'
        #         else:
        #             raise TypeError
        #         gql_args.append(item)
        #     return ', '.join(gql_args)
        #
        # if arguments is not None:
        #     self.arguments = parse_arguments(arguments)
        #
        #     if self.query_name.startswith('query'):
        #         self.arguments = 'filter: {' + self.arguments + '}'
        #
        #     self.arguments = '(' + self.arguments + ')'
        #
        # self.return_fields: list = return_fields
        #
        # self.return_fields_text: str = '{' + ",\n".join(return_fields) + '}'
        # self.query_text: str = (f'{{{self.query_name}{self.arguments} '
        #                         f'{self.return_fields_text}}}')

    # def post(self, endpoint: Endpoint = Endpoint('localhost:9080')) -> dict:
    #     """
    #     Query a given endpoint with this query.
    #
    #     :param endpoint: URL for endpoint. For standalone, use default ('localhost:9080')
    #     :type endpoint: str
    #     :return: JSON response from endpoint server.
    #     :rtype: dict
    #     """
    #     # response = requests.post(url=endpoint, data=self.query_text, headers=Endpoint.headers)
    #     # return response.json()
    #     return endpoint.send_query(self)


class Mutation(GraphQLOperation):
    def __init__(self, mutation_name: str, return_fields: list, arguments: dict = None):
        """
        Class for GraphQL mutations. See https://graphql.org/learn/queries/#mutations
        """
        valid_start_words: list[str] = ['add', 'delete', 'update']
        if not any([mutation_name.startswith(start) for start in valid_start_words]):
            raise AttributeError(f'Mutation name must start with one of the following: {valid_start_words}')
        else:
            super().__init__('mutation', mutation_name, return_fields, arguments)
