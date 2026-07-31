/* eslint-disable */
import { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';
export type Maybe<T> = T | null;
export type InputMaybe<T> = T | null | undefined;
export type Exact<T extends { [key: string]: unknown }> = {
  [K in keyof T]: T[K];
};
export type MakeOptional<T, K extends keyof T> = Omit<T, K> & {
  [SubKey in K]?: Maybe<T[SubKey]>;
};
export type MakeMaybe<T, K extends keyof T> = Omit<T, K> & {
  [SubKey in K]: Maybe<T[SubKey]>;
};
export type MakeEmpty<
  T extends { [key: string]: unknown },
  K extends keyof T,
> = { [_ in K]?: never };
export type Incremental<T> =
  | T
  | {
      [P in keyof T]?: P extends ' $fragmentName' | '__typename' ? T[P] : never;
    };
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string };
  String: { input: string; output: string };
  Boolean: { input: boolean; output: boolean };
  Int: { input: number; output: number };
  Float: { input: number; output: number };
  /** Date with time (isoformat) */
  DateTime: { input: string; output: string };
  /** The `JSON` scalar type represents JSON values as specified by [ECMA-404](https://ecma-international.org/wp-content/uploads/ECMA-404_2nd_edition_december_2017.pdf). */
  JSON: { input: unknown; output: unknown };
  UUID: { input: string; output: string };
};

export type AiRunType = {
  __typename?: 'AiRunType';
  completedAt?: Maybe<Scalars['DateTime']['output']>;
  createdAt: Scalars['DateTime']['output'];
  errorCode?: Maybe<Scalars['String']['output']>;
  id: Scalars['UUID']['output'];
  operation: Scalars['String']['output'];
  scanId: Scalars['UUID']['output'];
  startedAt?: Maybe<Scalars['DateTime']['output']>;
  status: Scalars['String']['output'];
};

export type AnalysisRevisionType = {
  __typename?: 'AnalysisRevisionType';
  createdAt: Scalars['DateTime']['output'];
  id: Scalars['UUID']['output'];
  revisionNumber: Scalars['Int']['output'];
  scanId: Scalars['UUID']['output'];
  status: Scalars['String']['output'];
};

export type CareResultType = {
  __typename?: 'CareResultType';
  data: Scalars['JSON']['output'];
  id: Scalars['UUID']['output'];
  language: Scalars['String']['output'];
  status: Scalars['String']['output'];
};

export type ConversationMessageConnection = {
  __typename?: 'ConversationMessageConnection';
  items: Array<ConversationMessageType>;
  pageInfo: PageInfo;
};

export type ConversationMessageType = {
  __typename?: 'ConversationMessageType';
  createdAt: Scalars['DateTime']['output'];
  id: Scalars['UUID']['output'];
  role: Scalars['String']['output'];
  status: Scalars['String']['output'];
  text: Scalars['String']['output'];
};

export type CurrentUserType = {
  __typename?: 'CurrentUserType';
  email: Scalars['String']['output'];
  id: Scalars['UUID']['output'];
  preferredLanguage: Scalars['String']['output'];
  role: Scalars['String']['output'];
};

export type GarmentAnalysisHistoryConnection = {
  __typename?: 'GarmentAnalysisHistoryConnection';
  items: Array<GarmentAnalysisHistoryType>;
  pageInfo: PageInfo;
};

export type GarmentAnalysisHistoryType = {
  __typename?: 'GarmentAnalysisHistoryType';
  createdAt: Scalars['DateTime']['output'];
  resultAvailable: Scalars['Boolean']['output'];
  scanId: Scalars['UUID']['output'];
  status: Scalars['String']['output'];
  thumbnailImageId?: Maybe<Scalars['UUID']['output']>;
  thumbnailScanId?: Maybe<Scalars['UUID']['output']>;
};

export type GarmentConnection = {
  __typename?: 'GarmentConnection';
  items: Array<GarmentType>;
  pageInfo: PageInfo;
};

export type GarmentDetailType = {
  __typename?: 'GarmentDetailType';
  activeAnalysis?: Maybe<AnalysisRevisionType>;
  activeResult?: Maybe<CareResultType>;
  analysedBefore: Scalars['Boolean']['output'];
  analyses: GarmentAnalysisHistoryConnection;
  cleanedBefore: Scalars['Boolean']['output'];
  displayName?: Maybe<Scalars['String']['output']>;
  id: Scalars['UUID']['output'];
  identifiers: Array<Scalars['String']['output']>;
  lastAnalysisAt?: Maybe<Scalars['DateTime']['output']>;
  serviceEvents: Array<ServiceEventType>;
  thumbnailImageId?: Maybe<Scalars['UUID']['output']>;
  thumbnailScanId?: Maybe<Scalars['UUID']['output']>;
};

export type GarmentHistoryConnection = {
  __typename?: 'GarmentHistoryConnection';
  items: Array<GarmentHistoryItemType>;
  pageInfo: PageInfo;
};

export type GarmentHistoryItemType = {
  __typename?: 'GarmentHistoryItemType';
  analysedBefore: Scalars['Boolean']['output'];
  cleanedBefore: Scalars['Boolean']['output'];
  id: Scalars['UUID']['output'];
  identifiers: Array<Scalars['String']['output']>;
  lastAnalysisAt?: Maybe<Scalars['DateTime']['output']>;
  thumbnailImageId?: Maybe<Scalars['UUID']['output']>;
  thumbnailScanId?: Maybe<Scalars['UUID']['output']>;
  thumbnailUrl?: Maybe<Scalars['String']['output']>;
};

export type GarmentType = {
  __typename?: 'GarmentType';
  activeResultId?: Maybe<Scalars['UUID']['output']>;
  archivedAt?: Maybe<Scalars['DateTime']['output']>;
  createdAt: Scalars['DateTime']['output'];
  displayName?: Maybe<Scalars['String']['output']>;
  id: Scalars['UUID']['output'];
};

export type IdentityCandidateType = {
  __typename?: 'IdentityCandidateType';
  classification: Scalars['String']['output'];
  garmentId: Scalars['UUID']['output'];
  id: Scalars['UUID']['output'];
  reasons: Scalars['JSON']['output'];
  status: Scalars['String']['output'];
  thumbnailImageId?: Maybe<Scalars['UUID']['output']>;
  thumbnailScanId?: Maybe<Scalars['UUID']['output']>;
};

export type PageInfo = {
  __typename?: 'PageInfo';
  nextCursor?: Maybe<Scalars['String']['output']>;
};

export type Query = {
  __typename?: 'Query';
  analysis?: Maybe<AnalysisRevisionType>;
  analysisRevision?: Maybe<AnalysisRevisionType>;
  currentUser: CurrentUserType;
  garment?: Maybe<GarmentType>;
  garmentDetail?: Maybe<GarmentDetailType>;
  garmentHistory: GarmentHistoryConnection;
  garments: GarmentConnection;
  imageMetadata: Array<ScanImageMetadataType>;
  messages: ConversationMessageConnection;
  run?: Maybe<AiRunType>;
  scan?: Maybe<ScanType>;
  scanResult?: Maybe<ResultCompositeType>;
  scans: ScanConnection;
  usage: UsageSummary;
};

export type QueryAnalysisArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryAnalysisRevisionArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryGarmentArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryGarmentDetailArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  first?: Scalars['Int']['input'];
  id: Scalars['UUID']['input'];
  language?: InputMaybe<Scalars['String']['input']>;
};

export type QueryGarmentHistoryArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  first?: Scalars['Int']['input'];
};

export type QueryGarmentsArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  first?: Scalars['Int']['input'];
};

export type QueryImageMetadataArgs = {
  scanId: Scalars['UUID']['input'];
};

export type QueryMessagesArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  first?: Scalars['Int']['input'];
  scanId: Scalars['UUID']['input'];
};

export type QueryRunArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryScanArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryScanResultArgs = {
  language?: InputMaybe<Scalars['String']['input']>;
  scanId: Scalars['UUID']['input'];
};

export type QueryScansArgs = {
  after?: InputMaybe<Scalars['String']['input']>;
  first?: Scalars['Int']['input'];
};

export type ResultCompositeType = {
  __typename?: 'ResultCompositeType';
  activeAnalysis?: Maybe<AnalysisRevisionType>;
  garment?: Maybe<GarmentType>;
  identityCandidates: Array<IdentityCandidateType>;
  result?: Maybe<CareResultType>;
  scan: ScanType;
};

export type ScanConnection = {
  __typename?: 'ScanConnection';
  items: Array<ScanType>;
  pageInfo: PageInfo;
};

export type ScanImageMetadataType = {
  __typename?: 'ScanImageMetadataType';
  displayOrder: Scalars['Int']['output'];
  height?: Maybe<Scalars['Int']['output']>;
  id: Scalars['UUID']['output'];
  role: Scalars['String']['output'];
  width?: Maybe<Scalars['Int']['output']>;
};

export type ScanType = {
  __typename?: 'ScanType';
  analysisStage?: Maybe<Scalars['String']['output']>;
  createdAt: Scalars['DateTime']['output'];
  errorCode?: Maybe<Scalars['String']['output']>;
  garmentId?: Maybe<Scalars['UUID']['output']>;
  id: Scalars['UUID']['output'];
  progressPercent: Scalars['Int']['output'];
  requestedLanguage: Scalars['String']['output'];
  status: Scalars['String']['output'];
};

export type ServiceEventType = {
  __typename?: 'ServiceEventType';
  createdAt: Scalars['DateTime']['output'];
  id: Scalars['UUID']['output'];
  kind: Scalars['String']['output'];
  note?: Maybe<Scalars['String']['output']>;
};

export type UsageSummary = {
  __typename?: 'UsageSummary';
  estimatedCostUsd: Scalars['String']['output'];
  modelRunCount: Scalars['Int']['output'];
};

export type ScanMessagesQueryVariables = Exact<{
  scanId: Scalars['UUID']['input'];
  first: Scalars['Int']['input'];
  after?: InputMaybe<Scalars['String']['input']>;
}>;

export type ScanMessagesQuery = {
  __typename?: 'Query';
  messages: {
    __typename?: 'ConversationMessageConnection';
    items: Array<{
      __typename?: 'ConversationMessageType';
      id: string;
      role: string;
      status: string;
      text: string;
      createdAt: string;
    }>;
    pageInfo: { __typename?: 'PageInfo'; nextCursor?: string | null };
  };
};

export type GarmentDetailQueryVariables = Exact<{
  garmentId: Scalars['UUID']['input'];
  first: Scalars['Int']['input'];
  after?: InputMaybe<Scalars['String']['input']>;
  language: Scalars['String']['input'];
}>;

export type GarmentDetailQuery = {
  __typename?: 'Query';
  garmentDetail?: {
    __typename?: 'GarmentDetailType';
    id: string;
    displayName?: string | null;
    identifiers: Array<string>;
    thumbnailScanId?: string | null;
    thumbnailImageId?: string | null;
    lastAnalysisAt?: string | null;
    analysedBefore: boolean;
    cleanedBefore: boolean;
    activeAnalysis?: {
      __typename?: 'AnalysisRevisionType';
      id: string;
      scanId: string;
      status: string;
      revisionNumber: number;
      createdAt: string;
    } | null;
    activeResult?: {
      __typename?: 'CareResultType';
      id: string;
      status: string;
      language: string;
      data: unknown;
    } | null;
    analyses: {
      __typename?: 'GarmentAnalysisHistoryConnection';
      items: Array<{
        __typename?: 'GarmentAnalysisHistoryType';
        scanId: string;
        status: string;
        createdAt: string;
        resultAvailable: boolean;
        thumbnailScanId?: string | null;
        thumbnailImageId?: string | null;
      }>;
      pageInfo: { __typename?: 'PageInfo'; nextCursor?: string | null };
    };
    serviceEvents: Array<{
      __typename?: 'ServiceEventType';
      id: string;
      kind: string;
      note?: string | null;
      createdAt: string;
    }>;
  } | null;
};

export type GarmentHistoryQueryVariables = Exact<{
  first: Scalars['Int']['input'];
  after?: InputMaybe<Scalars['String']['input']>;
}>;

export type GarmentHistoryQuery = {
  __typename?: 'Query';
  garmentHistory: {
    __typename?: 'GarmentHistoryConnection';
    items: Array<{
      __typename?: 'GarmentHistoryItemType';
      id: string;
      identifiers: Array<string>;
      thumbnailUrl?: string | null;
      thumbnailScanId?: string | null;
      thumbnailImageId?: string | null;
      lastAnalysisAt?: string | null;
      analysedBefore: boolean;
      cleanedBefore: boolean;
    }>;
    pageInfo: { __typename?: 'PageInfo'; nextCursor?: string | null };
  };
};

export type ScanImageMetadataQueryVariables = Exact<{
  scanId: Scalars['UUID']['input'];
}>;

export type ScanImageMetadataQuery = {
  __typename?: 'Query';
  imageMetadata: Array<{
    __typename?: 'ScanImageMetadataType';
    id: string;
    role: string;
    displayOrder: number;
    width?: number | null;
    height?: number | null;
  }>;
};

export type ResultCompositeQueryVariables = Exact<{
  scanId: Scalars['UUID']['input'];
  language: Scalars['String']['input'];
}>;

export type ResultCompositeQuery = {
  __typename?: 'Query';
  scanResult?: {
    __typename?: 'ResultCompositeType';
    scan: {
      __typename?: 'ScanType';
      id: string;
      status: string;
      requestedLanguage: string;
      progressPercent: number;
      analysisStage?: string | null;
      errorCode?: string | null;
      garmentId?: string | null;
      createdAt: string;
    };
    activeAnalysis?: {
      __typename?: 'AnalysisRevisionType';
      id: string;
      scanId: string;
      status: string;
      revisionNumber: number;
      createdAt: string;
    } | null;
    result?: {
      __typename?: 'CareResultType';
      id: string;
      status: string;
      language: string;
      data: unknown;
    } | null;
    garment?: {
      __typename?: 'GarmentType';
      id: string;
      displayName?: string | null;
      archivedAt?: string | null;
      activeResultId?: string | null;
      createdAt: string;
    } | null;
    identityCandidates: Array<{
      __typename?: 'IdentityCandidateType';
      id: string;
      garmentId: string;
      thumbnailScanId?: string | null;
      thumbnailImageId?: string | null;
      classification: string;
      reasons: unknown;
      status: string;
    }>;
  } | null;
};

export type ScanSummaryFragment = {
  __typename?: 'ScanType';
  id: string;
  status: string;
  requestedLanguage: string;
  progressPercent: number;
  analysisStage?: string | null;
  errorCode?: string | null;
  garmentId?: string | null;
  createdAt: string;
} & { ' $fragmentName'?: 'ScanSummaryFragment' };

export const ScanSummaryFragmentDoc = {
  kind: 'Document',
  definitions: [
    {
      kind: 'FragmentDefinition',
      name: { kind: 'Name', value: 'ScanSummary' },
      typeCondition: {
        kind: 'NamedType',
        name: { kind: 'Name', value: 'ScanType' },
      },
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          { kind: 'Field', name: { kind: 'Name', value: 'id' } },
          { kind: 'Field', name: { kind: 'Name', value: 'status' } },
          { kind: 'Field', name: { kind: 'Name', value: 'requestedLanguage' } },
          { kind: 'Field', name: { kind: 'Name', value: 'progressPercent' } },
          { kind: 'Field', name: { kind: 'Name', value: 'analysisStage' } },
          { kind: 'Field', name: { kind: 'Name', value: 'errorCode' } },
          { kind: 'Field', name: { kind: 'Name', value: 'garmentId' } },
          { kind: 'Field', name: { kind: 'Name', value: 'createdAt' } },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ScanSummaryFragment, unknown>;
export const ScanMessagesDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'query',
      name: { kind: 'Name', value: 'ScanMessages' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'scanId' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'UUID' } },
          },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'first' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'Int' } },
          },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'after' },
          },
          type: { kind: 'NamedType', name: { kind: 'Name', value: 'String' } },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'messages' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'scanId' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'scanId' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'first' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'first' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'after' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'after' },
                },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'items' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'role' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                      { kind: 'Field', name: { kind: 'Name', value: 'text' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'createdAt' },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'pageInfo' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'nextCursor' },
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<ScanMessagesQuery, ScanMessagesQueryVariables>;
export const GarmentDetailDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'query',
      name: { kind: 'Name', value: 'GarmentDetail' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'garmentId' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'UUID' } },
          },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'first' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'Int' } },
          },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'after' },
          },
          type: { kind: 'NamedType', name: { kind: 'Name', value: 'String' } },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'language' },
          },
          type: {
            kind: 'NonNullType',
            type: {
              kind: 'NamedType',
              name: { kind: 'Name', value: 'String' },
            },
          },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'garmentDetail' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'id' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'garmentId' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'first' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'first' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'after' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'after' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'language' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'language' },
                },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                { kind: 'Field', name: { kind: 'Name', value: 'displayName' } },
                { kind: 'Field', name: { kind: 'Name', value: 'identifiers' } },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'thumbnailScanId' },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'thumbnailImageId' },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'lastAnalysisAt' },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'analysedBefore' },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'cleanedBefore' },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'activeAnalysis' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'scanId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'revisionNumber' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'createdAt' },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'activeResult' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'language' },
                      },
                      { kind: 'Field', name: { kind: 'Name', value: 'data' } },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'analyses' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'items' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'scanId' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'status' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'createdAt' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'resultAvailable' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'thumbnailScanId' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'thumbnailImageId' },
                            },
                          ],
                        },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'pageInfo' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'nextCursor' },
                            },
                          ],
                        },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'serviceEvents' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'kind' } },
                      { kind: 'Field', name: { kind: 'Name', value: 'note' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'createdAt' },
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<GarmentDetailQuery, GarmentDetailQueryVariables>;
export const GarmentHistoryDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'query',
      name: { kind: 'Name', value: 'GarmentHistory' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'first' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'Int' } },
          },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'after' },
          },
          type: { kind: 'NamedType', name: { kind: 'Name', value: 'String' } },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'garmentHistory' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'first' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'first' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'after' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'after' },
                },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'items' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'identifiers' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'thumbnailUrl' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'thumbnailScanId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'thumbnailImageId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'lastAnalysisAt' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'analysedBefore' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'cleanedBefore' },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'pageInfo' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'nextCursor' },
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<GarmentHistoryQuery, GarmentHistoryQueryVariables>;
export const ScanImageMetadataDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'query',
      name: { kind: 'Name', value: 'ScanImageMetadata' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'scanId' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'UUID' } },
          },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'imageMetadata' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'scanId' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'scanId' },
                },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                { kind: 'Field', name: { kind: 'Name', value: 'role' } },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'displayOrder' },
                },
                { kind: 'Field', name: { kind: 'Name', value: 'width' } },
                { kind: 'Field', name: { kind: 'Name', value: 'height' } },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ScanImageMetadataQuery,
  ScanImageMetadataQueryVariables
>;
export const ResultCompositeDocument = {
  kind: 'Document',
  definitions: [
    {
      kind: 'OperationDefinition',
      operation: 'query',
      name: { kind: 'Name', value: 'ResultComposite' },
      variableDefinitions: [
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'scanId' },
          },
          type: {
            kind: 'NonNullType',
            type: { kind: 'NamedType', name: { kind: 'Name', value: 'UUID' } },
          },
        },
        {
          kind: 'VariableDefinition',
          variable: {
            kind: 'Variable',
            name: { kind: 'Name', value: 'language' },
          },
          type: {
            kind: 'NonNullType',
            type: {
              kind: 'NamedType',
              name: { kind: 'Name', value: 'String' },
            },
          },
        },
      ],
      selectionSet: {
        kind: 'SelectionSet',
        selections: [
          {
            kind: 'Field',
            name: { kind: 'Name', value: 'scanResult' },
            arguments: [
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'scanId' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'scanId' },
                },
              },
              {
                kind: 'Argument',
                name: { kind: 'Name', value: 'language' },
                value: {
                  kind: 'Variable',
                  name: { kind: 'Name', value: 'language' },
                },
              },
            ],
            selectionSet: {
              kind: 'SelectionSet',
              selections: [
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'scan' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'requestedLanguage' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'progressPercent' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'analysisStage' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'errorCode' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'garmentId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'createdAt' },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'activeAnalysis' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'scanId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'revisionNumber' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'createdAt' },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'result' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'language' },
                      },
                      { kind: 'Field', name: { kind: 'Name', value: 'data' } },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'garment' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'displayName' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'archivedAt' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'activeResultId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'createdAt' },
                      },
                    ],
                  },
                },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'identityCandidates' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'garmentId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'thumbnailScanId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'thumbnailImageId' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'classification' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'reasons' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'status' },
                      },
                    ],
                  },
                },
              ],
            },
          },
        ],
      },
    },
  ],
} as unknown as DocumentNode<
  ResultCompositeQuery,
  ResultCompositeQueryVariables
>;
