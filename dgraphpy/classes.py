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


class GraphQLOperation:
    def __init__(self, gql_type: str, name: str, return_fields: list, arguments: dict = None):
        """
        Class for GraphQL queries. See https://graphql.org/learn/queries/
        """
        self.name: str = name
        self.gql_type: str = gql_type

        def parse_arguments(args: dict) -> str:
            """
            Convert an arguments dictionary into a GraphQL-compatible string.

            :param args: arguments dictionary
            :type args: dict
            :return: GraphQL-compatible string
            :rtype: str
            """

            gql_args = []

            # TODO correctly handle list values e.g. for anyofterms
            for k, v in args.items():
                if isinstance(v, str):
                    v = f'"{str(v)}"' if k != 'has' else str(v)
                    item = str(k) + f': {v}'
                elif isinstance(v, dict):
                    v_text = parse_arguments(v)
                    item = str(k) + ': {' + v_text + '}'
                elif isinstance(v, list):
                    item = f'{k}: {", ".join(v)}'
                else:
                    raise TypeError
                gql_args.append(item)
            return ', '.join(gql_args)

        self.arguments = ''
        if arguments is not None:
            self.arguments: str = parse_arguments(arguments)

            # if self.arguments.startswith('filter'):
            #     pass
            # if self.name.startswith('query'):
            #     self.arguments = 'filter: {' + self.arguments + '}'

            self.arguments = '(' + self.arguments + ')'

        self.return_fields: list = return_fields
        self.return_fields_text: str = '{' + ",\n".join(return_fields) + '}'

        self.text: str = f'{self.gql_type} {self.name} ' + \
                         '{' + self.name + self.arguments + self.return_fields_text + '}'

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
