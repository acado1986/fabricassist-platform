import { gql } from '@apollo/client';
import {
  createApolloClient,
  refetchActiveGraphQLQueries,
} from '@fabricassist/api-client';

test('Apollo cache is memory-only and can be cleared between sessions', async () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  client.cache.writeQuery({
    query: gql`
      query CachedUser {
        currentUser {
          id
          email
          role
          preferredLanguage
        }
      }
    `,
    data: {
      currentUser: {
        __typename: 'CurrentUserType',
        id: 'user-1',
        email: 'customer@example.com',
        role: 'customer',
        preferredLanguage: 'en',
      },
    },
  });

  expect(
    Object.keys(client.cache.extract() as Record<string, unknown>),
  ).toContain('CurrentUserType:{"id":"user-1"}');
  await client.clearStore();
  expect(
    Object.keys(client.cache.extract() as Record<string, unknown>),
  ).toEqual([]);
});

test('REST cache effects refetch only active GraphQL queries', async () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const refetch = jest.fn().mockResolvedValue({});
  jest
    .spyOn(client, 'getObservableQueries')
    .mockReturnValue(
      new Map([['active', { queryName: 'GarmentHistory', refetch } as never]]),
    );

  await refetchActiveGraphQLQueries(client, [
    'GarmentHistory',
    'ScanImageMetadata',
  ]);

  expect(refetch).toHaveBeenCalledTimes(1);
});

test('Apollo merges paginated garment analysis history by scan id', () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const query = gql`
    query GarmentDetailPage($after: String) {
      garmentDetail(id: "garment-1", first: 1, after: $after) {
        id
        analyses {
          items {
            scanId
            resultAvailable
          }
          pageInfo {
            nextCursor
          }
        }
      }
    }
  `;
  client.cache.writeQuery({
    query,
    variables: { after: null },
    data: {
      garmentDetail: {
        __typename: 'GarmentDetailType',
        id: 'garment-1',
        analyses: {
          __typename: 'GarmentAnalysisHistoryConnection',
          items: [
            {
              __typename: 'GarmentAnalysisHistoryType',
              scanId: 'scan-1',
              resultAvailable: true,
            },
          ],
          pageInfo: { __typename: 'PageInfo', nextCursor: 'cursor-1' },
        },
      },
    },
  });
  client.cache.writeQuery({
    query,
    variables: { after: 'cursor-1' },
    data: {
      garmentDetail: {
        __typename: 'GarmentDetailType',
        id: 'garment-1',
        analyses: {
          __typename: 'GarmentAnalysisHistoryConnection',
          items: [
            {
              __typename: 'GarmentAnalysisHistoryType',
              scanId: 'scan-2',
              resultAvailable: false,
            },
          ],
          pageInfo: { __typename: 'PageInfo', nextCursor: null },
        },
      },
    },
  });

  const cached = client.cache.readQuery<{
    garmentDetail: { analyses: { items: { scanId: string }[] } };
  }>({ query, variables: { after: 'cursor-1' } });
  expect(
    cached?.garmentDetail.analyses.items.map((item) => item.scanId),
  ).toEqual(['scan-1', 'scan-2']);
});
