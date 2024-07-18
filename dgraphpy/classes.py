from __future__ import annotations

from dotenv import load_dotenv
import os

import requests


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
        if response.status_code == 200:
            resp_json = response.json()
            if 'errors' in list(resp_json.keys()):
                errors: list[dict] = resp_json["errors"]
                all_errors_text: str = "\n".join([error["message"] for error in errors])
                raise RuntimeError(f'Error raised by server: {all_errors_text}')
            return response.json()
        else:
            raise RuntimeError(f'HTTP status code was not 200 ({response.status_code})')


class Endpoint:
    def __init__(self, url: str):
        self.url: str = url

    def post(self, operation: GraphQLOperation):
        response = requests.post(url=self.url, data=operation.text, headers=Server.headers)
        return response.json()


class Schema:
    class SchemaAttribute:
        def __init__(self, name: str, attr_type: str, nullable: bool = True, directive: str = None):
            self.name: str = name
            self.attr_type: str = attr_type
            self.nullable: bool = nullable
            self.directive: str = directive

            nullable_text: str = "!" if self.nullable else ""
            directive_text: str = f' @{self.directive}' if self.directive else ''
            self.text: str = f'{self.name}: {self.attr_type}{nullable_text}{directive_text}'

        @staticmethod
        def remove_trailing_comment(text: str) -> str:
            """
            Remove comment and trailing whitespace from a line of text.

            :param text: A line of text.
            :type text: str
            :return: The text with comment and trailing whitespace removed
            :rtype: str
            """
            text = text.split('#')[0].rstrip()
            return text

        @classmethod
        def from_text(cls, text) -> Schema.SchemaAttribute:
            chunks: list[str] = [chunk.strip() for chunk in text.split(':')]

            name: str = chunks[0].replace(',', '')

            attr_details = chunks[1].split('@')
            attr_type: str = attr_details[0].replace('!', '').replace(',', '').strip()
            can_be_null: bool = False if '!' in chunks[1] else True

            if '@' in chunks[1]:
                directive: str | None = Schema.SchemaAttribute.remove_trailing_comment(text.split('@')[1])
            else:
                directive = None

            attr: Schema.SchemaAttribute = cls(name, attr_type, can_be_null, directive)
            return attr

    class SchemaType:
        def __init__(self, name: str, attributes: list[Schema.SchemaAttribute]):
            self.name: str = name
            self.attributes: list[Schema.SchemaAttribute] = attributes

        def __repr__(self):
            attrs_text: str = "\n".join([f'\t- {attr.text}' for attr in self.attributes])
            return f'SchemaType called "{self.name}" with attributes:\n{attrs_text}'

        @classmethod
        def from_text(cls, text: str) -> Schema.SchemaType:
            chunks: list[str] = [chunk.strip() for chunk in text.split('\n')
                                 if not (chunk == '' or chunk.strip().startswith('#'))]

            name: str = chunks[0].replace('type ', '').split(' ')[0]  # remove "type " then get first word
            attributes = [chunk for chunk in chunks[1:] if chunk not in ['{', '}']]
            attribute_objs: list[Schema.SchemaAttribute] = [Schema.SchemaAttribute.from_text(line)
                                                            for line in attributes]

            schema_type = cls(name, attribute_objs)
            return schema_type

    class SchemaEnum:
        def __init__(self, name: str, options: list[str]):
            self.name: str = name
            self.options: list[str] = options

        def __repr__(self):
            options_text: str = "\n".join([f'\t- {option}' for option in self.options])
            return f'SchemaEnum called "{self.name}" with options:\n{options_text}'

        @classmethod
        def from_text(cls, text: str) -> Schema.SchemaEnum:
            item_chunks: list[str] = [chunk.strip() for chunk in text.split('{')]
            item_chunks = Schema.remove_comment_lines(item_chunks, True)

            name = item_chunks[0].replace('enum ', '')  # just get enum's name

            # split options chunk into lines, remove } and remove whitespace at start or end of option
            options: list[str] = [chunk.strip() for chunk in item_chunks[1].split('\n') if chunk != '}']

            enum: Schema.SchemaEnum = cls(name, options)
            return enum

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

        # if schema made by "schema" query, returned text is equivalent to input_schema from a "generatedSchema" query.
        if schema_chunks is None:
            self.input_schema: str = self.text

        # Attributes for storing data about the data in the schema text
        self.types = self.get_types()

    def get_types(self) -> list:
        """
        Get a list of the types within the schema.

        :return: List of SchemaType objects representing each type entry in the schema.
        :rtype: SchemaType
        """
        types: list = [item.strip() for item in self.input_schema.split('}\n')]
        types = self.remove_comment_lines(types, remove_blank_lines=True)

        type_objs: list[Schema.SchemaType | Schema.SchemaEnum] = []
        for item in types:
            if item.startswith('type'):
                type_objs.append(Schema.SchemaType.from_text(item))
            elif item.startswith('enum'):
                type_objs.append(Schema.SchemaEnum.from_text(item))
            else:
                raise AttributeError(f'Item in schema not recognised as type or enum:\n{item}')

        self.types: list[Schema.SchemaType | Schema.SchemaEnum] = type_objs  # update schema's classes attribute
        return self.types

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

    @staticmethod
    def remove_comment_lines(text_lines: list[str], remove_blank_lines: bool = False) -> list[str]:
        new_lines: list[str] = [item for item in text_lines if not item.startswith('#')]
        if remove_blank_lines:
            new_lines = [line for line in new_lines if line != '']
        return new_lines


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
