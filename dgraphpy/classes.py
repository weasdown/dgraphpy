from __future__ import annotations

import requests


class Endpoint:
    headers: dict = {
        "Content-Type": "application/graphql",
    }

    def __init__(self, url: str):
        self.url: str = url

    def query(self, query: Query):
        pass

    def send_query(self, query: Query) -> dict:
        """
        Run a given query.

        :param query:
        :type query:
        :return: JSON response from endpoint server.
        :rtype: dict
        """
        response = requests.post(url=self.url, data=query.query_text, headers=Endpoint.headers)
        return response.json()

    def send_mutation(self, mutation: Mutation) -> dict:
        """
        Run a given mutation.

        :param mutation:
        :type mutation:
        :return: JSON response from endpoint server.
        :rtype: dict
        """
        response = requests.post(url=self.url, data=mutation.mutation_text, headers=Endpoint.headers)
        return response.json()


class Query:
    def __init__(self, query_name: str, return_fields: list, arguments: dict = None):
        """
        Class for GraphQL queries. See https://graphql.org/learn/queries/
        """
        self.query_name: str = query_name
        self.arguments: str = str(', '.join([f'{k}: "{v}"' for (k, v) in arguments.items()])) \
            if arguments is not None else None
        self.return_fields: list = return_fields

        self.return_fields_text: str = '{' + ",\n".join(return_fields) + '}'
        self.query_text: str = (f'{{{self.query_name}{"" if self.arguments is None else f"({self.arguments})"} '
                                f'{self.return_fields_text}}}')

    def post(self, endpoint: Endpoint = Endpoint('localhost:9080')) -> dict:
        """
        Query a given endpoint with this query.

        :param endpoint: URL for endpoint. For standalone, use default ('localhost:9080')
        :type endpoint: str
        :return: JSON response from endpoint server.
        :rtype: dict
        """
        # response = requests.post(url=endpoint, data=self.query_text, headers=Endpoint.headers)
        # return response.json()
        return endpoint.send_query(self)


class Mutation:
    def __init__(self):
        """
        Class for GraphQL mutations. See https://graphql.org/learn/queries/#mutations
        """
        self.mutation_text: str = ...
        raise NotImplementedError()
