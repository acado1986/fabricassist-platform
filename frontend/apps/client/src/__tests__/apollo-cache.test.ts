import { gql } from '@apollo/client';
import {
  applyRestWriteCacheEffect,
  createApolloClient,
  REST_WRITE_REGISTRY,
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

test('REST cache effects do not reject when an active query is stale', async () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const refetch = jest.fn().mockRejectedValue(new Error('NOT_FOUND'));
  jest
    .spyOn(client, 'getObservableQueries')
    .mockReturnValue(
      new Map([
        ['active', { queryName: 'ScanImageMetadata', refetch } as never],
      ]),
    );

  await expect(
    refetchActiveGraphQLQueries(client, ['ScanImageMetadata']),
  ).resolves.toBeUndefined();
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

test('Apollo replaces the canonical first garment-history page', () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const query = gql`
    query GarmentHistoryPage($after: String) {
      garmentHistory(first: 20, after: $after) {
        items {
          id
        }
        pageInfo {
          nextCursor
        }
      }
    }
  `;
  const item = (id: string) => ({
    __typename: 'GarmentHistoryItemType',
    id,
  });

  client.cache.writeQuery({
    query,
    variables: { after: null },
    data: {
      garmentHistory: {
        __typename: 'GarmentHistoryConnection',
        items: [item('deleted-garment')],
        pageInfo: { __typename: 'PageInfo', nextCursor: null },
      },
    },
  });
  client.cache.writeQuery({
    query,
    variables: { after: null },
    data: {
      garmentHistory: {
        __typename: 'GarmentHistoryConnection',
        items: [item('new-garment')],
        pageInfo: { __typename: 'PageInfo', nextCursor: null },
      },
    },
  });

  const cached = client.cache.readQuery<{
    garmentHistory: { items: { id: string }[] };
  }>({ query, variables: { after: null } });
  expect(cached?.garmentHistory.items.map(({ id }) => id)).toEqual([
    'new-garment',
  ]);
});

test('mixed cache effects synchronize every declared projection', async () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const resultQuery = jest
    .spyOn(client, 'query')
    .mockResolvedValue({ data: {} } as never);
  const detailRefetch = jest.fn().mockResolvedValue({});
  const historyRefetch = jest.fn().mockResolvedValue({});
  jest.spyOn(client, 'getObservableQueries').mockReturnValue(
    new Map([
      [
        'detail',
        { queryName: 'GarmentDetail', refetch: detailRefetch } as never,
      ],
      [
        'history',
        { queryName: 'GarmentHistory', refetch: historyRefetch } as never,
      ],
    ]),
  );

  await applyRestWriteCacheEffect(
    'confirmIdentity',
    REST_WRITE_REGISTRY.confirmIdentity,
    { apolloClient: client, scanId: 'scan-1', language: 'es' },
  );

  expect(resultQuery).toHaveBeenCalledWith(
    expect.objectContaining({
      variables: { scanId: 'scan-1', language: 'es' },
      fetchPolicy: 'network-only',
    }),
  );
  expect(detailRefetch).toHaveBeenCalledTimes(1);
  expect(historyRefetch).toHaveBeenCalledTimes(1);
});

test('garment deletion evicts normalized detail and history entries and refetches only surviving history', async () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const query = gql`
    query GarmentDeletionSnapshot($after: String) {
      garmentHistory(first: 20, after: $after) {
        items {
          id
          identifiers
        }
        pageInfo {
          nextCursor
        }
      }
      garmentDetail(id: "garment-1", first: 20, after: $after, language: "en") {
        id
        displayName
        analyses {
          items {
            scanId
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
      garmentHistory: {
        __typename: 'GarmentHistoryConnection',
        items: [
          {
            __typename: 'GarmentHistoryItemType',
            id: 'garment-1',
            identifiers: [],
          },
        ],
        pageInfo: { __typename: 'PageInfo', nextCursor: null },
      },
      garmentDetail: {
        __typename: 'GarmentDetailType',
        id: 'garment-1',
        displayName: 'Old garment',
        analyses: {
          __typename: 'GarmentAnalysisHistoryConnection',
          items: [],
          pageInfo: { __typename: 'PageInfo', nextCursor: null },
        },
      },
    },
  });
  const querySpy = jest
    .spyOn(client, 'query')
    .mockResolvedValue({ data: {} } as never);
  const gcSpy = jest.spyOn(client.cache, 'gc');
  await applyRestWriteCacheEffect(
    'deleteGarment',
    REST_WRITE_REGISTRY.deleteGarment,
    {
      apolloClient: client,
      garmentId: 'garment-1',
    },
  );

  const garmentCacheId = client.cache.identify({
    __typename: 'GarmentType',
    id: 'garment-1',
  });
  expect(garmentCacheId).toBeDefined();
  expect(client.cache.extract()).not.toHaveProperty(garmentCacheId!);
  expect(client.cache.extract()).not.toHaveProperty(
    'GarmentHistoryItemType:garment-1',
  );
  expect(
    client.cache.readQuery({ query, variables: { after: null } }),
  ).toBeNull();
  expect(gcSpy).toHaveBeenCalled();
  expect(querySpy).toHaveBeenCalledWith(
    expect.objectContaining({ fetchPolicy: 'network-only' }),
  );
});

test('cancel cache effect performs canonical network-only result synchronization even without an active query', async () => {
  const client = createApolloClient({
    endpoint: 'http://localhost:8000/api/v1/graphql',
    getAccessToken: () => 'token',
    refreshAccessToken: async () => null,
  });
  const querySpy = jest
    .spyOn(client, 'query')
    .mockResolvedValue({ data: {} } as never);
  await applyRestWriteCacheEffect('cancelRun', REST_WRITE_REGISTRY.cancelRun, {
    apolloClient: client,
    scanId: 'scan-1',
    language: 'es',
  });

  expect(querySpy).toHaveBeenCalledWith(
    expect.objectContaining({
      variables: { scanId: 'scan-1', language: 'es' },
      fetchPolicy: 'network-only',
    }),
  );
});
