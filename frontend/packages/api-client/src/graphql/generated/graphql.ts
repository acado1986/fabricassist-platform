/* eslint-disable */
import { DocumentTypeDecoration } from '@graphql-typed-document-node/core';
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

export type CreateScanInput = {
  requestedLanguage?: Scalars['String']['input'];
};

export type CurrentUserType = {
  __typename?: 'CurrentUserType';
  email: Scalars['String']['output'];
  id: Scalars['UUID']['output'];
  preferredLanguage: Scalars['String']['output'];
  role: Scalars['String']['output'];
};

export type FeedbackType = {
  __typename?: 'FeedbackType';
  id: Scalars['UUID']['output'];
  requestReview: Scalars['Boolean']['output'];
};

export type GarmentConnection = {
  __typename?: 'GarmentConnection';
  items: Array<GarmentType>;
  pageInfo: PageInfo;
};

export type GarmentIdInput = {
  garmentId: Scalars['UUID']['input'];
};

export type GarmentType = {
  __typename?: 'GarmentType';
  activeResultId?: Maybe<Scalars['UUID']['output']>;
  archivedAt?: Maybe<Scalars['DateTime']['output']>;
  createdAt: Scalars['DateTime']['output'];
  displayName?: Maybe<Scalars['String']['output']>;
  id: Scalars['UUID']['output'];
};

export type Mutation = {
  __typename?: 'Mutation';
  archiveGarment: GarmentType;
  createScan: ScanType;
  deleteGarment: Scalars['Boolean']['output'];
  deleteScan: Scalars['Boolean']['output'];
  renameGarment: GarmentType;
  submitFeedback: FeedbackType;
  unarchiveGarment: GarmentType;
};

export type MutationArchiveGarmentArgs = {
  input: GarmentIdInput;
};

export type MutationCreateScanArgs = {
  input: CreateScanInput;
};

export type MutationDeleteGarmentArgs = {
  input: GarmentIdInput;
};

export type MutationDeleteScanArgs = {
  input: ScanIdInput;
};

export type MutationRenameGarmentArgs = {
  input: RenameGarmentInput;
};

export type MutationSubmitFeedbackArgs = {
  input: SubmitFeedbackInput;
};

export type MutationUnarchiveGarmentArgs = {
  input: GarmentIdInput;
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
  garments: GarmentConnection;
  imageMetadata: Array<ScanImageMetadataType>;
  messages: ConversationMessageConnection;
  run?: Maybe<AiRunType>;
  scan?: Maybe<ScanType>;
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

export type QueryGarmentsArgs = {
  after?: InputMaybe<Scalars['UUID']['input']>;
  first?: Scalars['Int']['input'];
};

export type QueryImageMetadataArgs = {
  scanId: Scalars['UUID']['input'];
};

export type QueryMessagesArgs = {
  after?: InputMaybe<Scalars['UUID']['input']>;
  first?: Scalars['Int']['input'];
  scanId: Scalars['UUID']['input'];
};

export type QueryRunArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryScanArgs = {
  id: Scalars['UUID']['input'];
};

export type QueryScansArgs = {
  after?: InputMaybe<Scalars['UUID']['input']>;
  first?: Scalars['Int']['input'];
};

export type RenameGarmentInput = {
  displayName: Scalars['String']['input'];
  garmentId: Scalars['UUID']['input'];
};

export type ScanConnection = {
  __typename?: 'ScanConnection';
  items: Array<ScanType>;
  pageInfo: PageInfo;
};

export type ScanIdInput = {
  scanId: Scalars['UUID']['input'];
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

export type SubmitFeedbackInput = {
  comment?: InputMaybe<Scalars['String']['input']>;
  rating?: InputMaybe<Scalars['Int']['input']>;
  requestReview?: Scalars['Boolean']['input'];
  scanId: Scalars['UUID']['input'];
};

export type UsageSummary = {
  __typename?: 'UsageSummary';
  estimatedCostUsd: Scalars['String']['output'];
  modelRunCount: Scalars['Int']['output'];
};

export type ScanMessagesQueryVariables = Exact<{
  scanId: Scalars['UUID']['input'];
  first: Scalars['Int']['input'];
  after?: InputMaybe<Scalars['UUID']['input']>;
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

export type ScanHistoryQueryVariables = Exact<{
  first: Scalars['Int']['input'];
  after?: InputMaybe<Scalars['UUID']['input']>;
}>;

export type ScanHistoryQuery = {
  __typename?: 'Query';
  scans: {
    __typename?: 'ScanConnection';
    items: Array<
      { __typename?: 'ScanType' } & {
        ' $fragmentRefs'?: { ScanSummaryFragment: ScanSummaryFragment };
      }
    >;
    pageInfo: { __typename?: 'PageInfo'; nextCursor?: string | null };
  };
};

export type ScanRunRecoveryQueryVariables = Exact<{
  id: Scalars['UUID']['input'];
}>;

export type ScanRunRecoveryQuery = {
  __typename?: 'Query';
  scan?:
    | ({ __typename?: 'ScanType' } & {
        ' $fragmentRefs'?: { ScanSummaryFragment: ScanSummaryFragment };
      })
    | null;
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

export class TypedDocumentString<TResult, TVariables>
  extends String
  implements DocumentTypeDecoration<TResult, TVariables>
{
  __apiType?: NonNullable<
    DocumentTypeDecoration<TResult, TVariables>['__apiType']
  >;
  private value: string;
  public __meta__?: Record<string, any> | undefined;

  constructor(value: string, __meta__?: Record<string, any> | undefined) {
    super(value);
    this.value = value;
    this.__meta__ = __meta__;
  }

  override toString(): string & DocumentTypeDecoration<TResult, TVariables> {
    return this.value;
  }
}
export const ScanSummaryFragmentDoc = new TypedDocumentString(
  `
    fragment ScanSummary on ScanType {
  id
  status
  requestedLanguage
  progressPercent
  analysisStage
  errorCode
  garmentId
  createdAt
}
    `,
  { fragmentName: 'ScanSummary' },
) as unknown as TypedDocumentString<ScanSummaryFragment, unknown>;
export const ScanMessagesDocument = new TypedDocumentString(`
    query ScanMessages($scanId: UUID!, $first: Int!, $after: UUID) {
  messages(scanId: $scanId, first: $first, after: $after) {
    items {
      id
      role
      status
      text
      createdAt
    }
    pageInfo {
      nextCursor
    }
  }
}
    `) as unknown as TypedDocumentString<
  ScanMessagesQuery,
  ScanMessagesQueryVariables
>;
export const ScanHistoryDocument = new TypedDocumentString(`
    query ScanHistory($first: Int!, $after: UUID) {
  scans(first: $first, after: $after) {
    items {
      ...ScanSummary
    }
    pageInfo {
      nextCursor
    }
  }
}
    fragment ScanSummary on ScanType {
  id
  status
  requestedLanguage
  progressPercent
  analysisStage
  errorCode
  garmentId
  createdAt
}`) as unknown as TypedDocumentString<
  ScanHistoryQuery,
  ScanHistoryQueryVariables
>;
export const ScanRunRecoveryDocument = new TypedDocumentString(`
    query ScanRunRecovery($id: UUID!) {
  scan(id: $id) {
    ...ScanSummary
  }
}
    fragment ScanSummary on ScanType {
  id
  status
  requestedLanguage
  progressPercent
  analysisStage
  errorCode
  garmentId
  createdAt
}`) as unknown as TypedDocumentString<
  ScanRunRecoveryQuery,
  ScanRunRecoveryQueryVariables
>;
