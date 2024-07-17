from __future__ import annotations

from dotenv import load_dotenv
import os

import requests
import json


class Server:
    headers: dict = {
        "Content-Type": "application/graphql",
    }

    def __init__(self, url: str):
        self.url: str = url
        self.admin_endpoint: str = f'{self.url}/admin'
        self.graphql_endpoint: str = f'{self.url}/graphql'
        self.alter_endpoint: str = f'{self.url}/alter'

    def post(self, endpoint_url: str, operation: GraphQLOperation) -> dict:
        if endpoint_url not in [self.admin_endpoint, self.graphql_endpoint, self.alter_endpoint]:
            raise AttributeError

        headers = getattr(operation, 'headers', Server.headers)

        response = requests.post(url=endpoint_url, data=operation.text, headers=headers)
        return response.json()


class Endpoint:
    def __init__(self, url: str):
        self.url: str = url

    def post(self, operation: GraphQLOperation):
        response = requests.post(url=self.url, data=operation.text, headers=Server.headers)
        return response.json()


class Schema:
    def __init__(self, schema_text: str):
        self.text: str = schema_text

        schema_chunks = schema_text.split('#######################') \
            if '#######################' in schema_text else None
        schema_chunks = [chunk.removeprefix('\n\n').removesuffix('\n\n') for chunk in schema_chunks] \
            if schema_chunks is not None else None

        attrs = ['input_schema', 'extended_definitions', 'generated_types', 'generated_enums', 'generated_inputs',
                 'generated_query', 'generated_mutations']
        for index, attr in enumerate(attrs):
            # Set attributes for schema chunks. Only valid if text built by generatedSchema query (not just schema).
            # Example: self.extended_definitions = schema_chunks[4]
            setattr(self, attr, schema_chunks[(index + 1) * 2] if schema_chunks is not None else None)

    @classmethod
    def from_SchemaQuery(cls, query: SchemaQuery, server: Server) -> 'Schema':
        """
        Build a Schema object from a SchemaQuery that pulls schema information from the server.

        :param query: Query specifying which details of the schema should be retrieved from the server.
        :type query: SchemaQuery
        :param server: Server from which to get schema information.
        :type server: Server
        :return: Schema object
        :rtype: Schema
        """
        response: dict = server.post(server.admin_endpoint, query)
        schema_data: dict = response['data']['getGQLSchema']

        # Pull schema text from response dict. Dict key varies depending on query used to get schema data,
        # so use query.text to determine corrected key to use
        schema_text: str = schema_data.get('generatedSchema').replace('\u2010', '-') if 'generatedSchema' in query.text\
            else schema_data.get('schema')

        schema = cls(schema_text)  # make a Schema obejct from the schema_text
        return schema


class GraphQLOperation:
    def __init__(self, gql_type: str, return_fields: list, name: str = None, arguments: dict = None):
        """
        Class for GraphQL queries. See https://graphql.org/learn/queries/
        """
        self.name: str = name if name is not None else ''
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

        self.headers: dict | None = None

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
            super().__init__('query', return_fields, query_name, arguments)


# TODO add upsert ability
class Mutation(GraphQLOperation):
    def __init__(self, mutation_name: str, return_fields: list, arguments: dict = None):
        """
        Class for GraphQL mutations. See https://graphql.org/learn/queries/#mutations
        """
        valid_start_words: list[str] = ['add', 'delete', 'update']
        if not any([mutation_name.startswith(start) for start in valid_start_words]):
            raise AttributeError(f'Mutation name must start with one of the following: {valid_start_words}')
        else:
            super().__init__('mutation', return_fields, mutation_name, arguments)


class SchemaQuery(GraphQLOperation):
    def __init__(self, return_fields: list = None, predicates: list[str] = None, generated_schema: bool = False):
        return_fields = [''] if return_fields is None else return_fields
        predicates: dict = {'pred': predicates} if predicates is not None else None
        super().__init__('schema', return_fields, arguments=predicates)

        self.text = '{ getGQLSchema { ' + ('generatedSchema' if generated_schema else 'schema') + ' } }'

        # self.text: str = 'schema {' + '\n'.join(return_fields) + '}'  # FIXME
        self.headers: dict = Server.headers

        # Load X-Auth-Token API token from .env in same directory as this file
        load_dotenv()
        x_auth_token: str = os.getenv('X_AUTH_TOKEN')
        self.headers['X-Auth-Token'] = x_auth_token
