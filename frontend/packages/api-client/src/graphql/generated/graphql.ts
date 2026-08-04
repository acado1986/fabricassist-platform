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

export type AnalysisBranchSummaryType = {
  __typename?: 'AnalysisBranchSummaryType';
  branch: Scalars['String']['output'];
  schemaVersion?: Maybe<Scalars['String']['output']>;
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

export type CareActionType = {
  __typename?: 'CareActionType';
  code: Scalars['String']['output'];
  evidencePaths: Array<Scalars['String']['output']>;
  maximumTemperatureC?: Maybe<Scalars['Int']['output']>;
  permission: Scalars['String']['output'];
  process?: Maybe<Scalars['String']['output']>;
  professionalOnly: Scalars['Boolean']['output'];
  reasonKey: Scalars['String']['output'];
};

export type CareResultType = {
  __typename?: 'CareResultType';
  id: Scalars['UUID']['output'];
  result: GarmentAnalysisResultType;
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

export type EvidenceConflictType = {
  __typename?: 'EvidenceConflictType';
  explanationKey: Scalars['String']['output'];
  fieldPath: Scalars['String']['output'];
  id: Scalars['UUID']['output'];
  resolutionCode: Scalars['String']['output'];
  selectedValue?: Maybe<Scalars['String']['output']>;
  severity: Scalars['String']['output'];
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

export type GarmentAnalysisResultType = {
  __typename?: 'GarmentAnalysisResultType';
  allowedActions: Array<CareActionType>;
  branches: Array<AnalysisBranchSummaryType>;
  category: Scalars['String']['output'];
  clearerImageRequests: Array<Scalars['String']['output']>;
  colors: Array<Scalars['String']['output']>;
  conflicts: Array<EvidenceConflictType>;
  features: Array<Scalars['String']['output']>;
  historyEventIds: Array<Scalars['UUID']['output']>;
  issues: Array<GarmentIssueType>;
  labelWarnings: Array<Scalars['String']['output']>;
  materials: Array<MaterialType>;
  outcome: Scalars['String']['output'];
  overallCondition: Scalars['String']['output'];
  pattern: Scalars['String']['output'];
  preferenceSource: Scalars['String']['output'];
  productBarcode?: Maybe<Scalars['String']['output']>;
  productFacts?: Maybe<Scalars['JSON']['output']>;
  productLookupStatus: Scalars['String']['output'];
  productSource?: Maybe<Scalars['String']['output']>;
  professionalOnlyActions: Array<CareActionType>;
  prohibitedActions: Array<CareActionType>;
  schemaVersion: Scalars['String']['output'];
  stainSteps: Array<StainStepType>;
  subtype?: Maybe<Scalars['String']['output']>;
  uncertainties: Array<Scalars['String']['output']>;
  unknownActions: Array<CareActionType>;
  versions: Array<VersionType>;
  visibleLabelText: Array<LabelTextType>;
  warnings: Array<Scalars['String']['output']>;
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
  observations: Array<GarmentObservationType>;
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

export type GarmentIssueType = {
  __typename?: 'GarmentIssueType';
  causeState: Scalars['String']['output'];
  confidence: Scalars['Int']['output'];
  confirmedCause?: Maybe<Scalars['String']['output']>;
  id: Scalars['UUID']['output'];
  kind: Scalars['String']['output'];
  location: Scalars['String']['output'];
  observedDescription: Scalars['String']['output'];
  severity: Scalars['String']['output'];
  sourceImageIds: Array<Scalars['UUID']['output']>;
  suspectedCauses: Array<Scalars['String']['output']>;
};

export type GarmentObservationType = {
  __typename?: 'GarmentObservationType';
  analysisRevisionId: Scalars['UUID']['output'];
  authority: Scalars['String']['output'];
  confidence?: Maybe<Scalars['Float']['output']>;
  createdAt: Scalars['DateTime']['output'];
  evidenceIds: Array<Scalars['UUID']['output']>;
  id: Scalars['UUID']['output'];
  observationType: Scalars['String']['output'];
  stability: Scalars['String']['output'];
  supersedesObservationId?: Maybe<Scalars['UUID']['output']>;
  value: Scalars['JSON']['output'];
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

export type LabelTextType = {
  __typename?: 'LabelTextType';
  confidence: Scalars['Int']['output'];
  imageId: Scalars['UUID']['output'];
  language: Scalars['String']['output'];
  text: Scalars['String']['output'];
};

export type MaterialType = {
  __typename?: 'MaterialType';
  confidence: Scalars['Int']['output'];
  material: Scalars['String']['output'];
  percentage?: Maybe<Scalars['Float']['output']>;
  sourceImageIds: Array<Scalars['UUID']['output']>;
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
  labelScope?: Maybe<Scalars['String']['output']>;
  qualityState?: Maybe<Scalars['String']['output']>;
  role: Scalars['String']['output'];
  viewpoint?: Maybe<Scalars['String']['output']>;
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

export type StainStepType = {
  __typename?: 'StainStepType';
  actionCode: Scalars['String']['output'];
  claimId: Scalars['UUID']['output'];
  status: Scalars['String']['output'];
  text?: Maybe<Scalars['String']['output']>;
  violationCodes: Array<Scalars['String']['output']>;
};

export type UsageSummary = {
  __typename?: 'UsageSummary';
  estimatedCostUsd: Scalars['String']['output'];
  modelRunCount: Scalars['Int']['output'];
};

export type VersionType = {
  __typename?: 'VersionType';
  name: Scalars['String']['output'];
  value: Scalars['String']['output'];
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
      result: {
        __typename?: 'GarmentAnalysisResultType';
        outcome: string;
        category: string;
        overallCondition: string;
        warnings: Array<string>;
        clearerImageRequests: Array<string>;
        uncertainties: Array<string>;
        allowedActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
        }>;
        prohibitedActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
        }>;
        unknownActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
        }>;
        professionalOnlyActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
        }>;
        conflicts: Array<{
          __typename?: 'EvidenceConflictType';
          id: string;
          fieldPath: string;
          severity: string;
          explanationKey: string;
        }>;
      };
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
    observations: Array<{
      __typename?: 'GarmentObservationType';
      id: string;
      observationType: string;
      stability: string;
      authority: string;
      value: unknown;
      evidenceIds: Array<string>;
      confidence?: number | null;
      analysisRevisionId: string;
      supersedesObservationId?: string | null;
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
    viewpoint?: string | null;
    labelScope?: string | null;
    qualityState?: string | null;
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
      result: {
        __typename?: 'GarmentAnalysisResultType';
        schemaVersion: string;
        outcome: string;
        warnings: Array<string>;
        category: string;
        subtype?: string | null;
        colors: Array<string>;
        pattern: string;
        features: Array<string>;
        overallCondition: string;
        labelWarnings: Array<string>;
        uncertainties: Array<string>;
        clearerImageRequests: Array<string>;
        historyEventIds: Array<string>;
        preferenceSource: string;
        productBarcode?: string | null;
        productLookupStatus: string;
        productSource?: string | null;
        productFacts?: unknown | null;
        issues: Array<{
          __typename?: 'GarmentIssueType';
          id: string;
          kind: string;
          severity: string;
          location: string;
          observedDescription: string;
          confidence: number;
          suspectedCauses: Array<string>;
          confirmedCause?: string | null;
          causeState: string;
        }>;
        visibleLabelText: Array<{
          __typename?: 'LabelTextType';
          imageId: string;
          text: string;
          language: string;
          confidence: number;
        }>;
        materials: Array<{
          __typename?: 'MaterialType';
          material: string;
          percentage?: number | null;
          confidence: number;
        }>;
        allowedActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
          process?: string | null;
          reasonKey: string;
          professionalOnly: boolean;
        }>;
        prohibitedActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
          process?: string | null;
          reasonKey: string;
          professionalOnly: boolean;
        }>;
        unknownActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
          process?: string | null;
          reasonKey: string;
          professionalOnly: boolean;
        }>;
        professionalOnlyActions: Array<{
          __typename?: 'CareActionType';
          code: string;
          permission: string;
          maximumTemperatureC?: number | null;
          process?: string | null;
          reasonKey: string;
          professionalOnly: boolean;
        }>;
        conflicts: Array<{
          __typename?: 'EvidenceConflictType';
          id: string;
          fieldPath: string;
          selectedValue?: string | null;
          resolutionCode: string;
          explanationKey: string;
          severity: string;
        }>;
        branches: Array<{
          __typename?: 'AnalysisBranchSummaryType';
          branch: string;
          status: string;
          schemaVersion?: string | null;
        }>;
        stainSteps: Array<{
          __typename?: 'StainStepType';
          claimId: string;
          status: string;
          text?: string | null;
          actionCode: string;
          violationCodes: Array<string>;
        }>;
        versions: Array<{
          __typename?: 'VersionType';
          name: string;
          value: string;
        }>;
      };
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
                        name: { kind: 'Name', value: 'result' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'outcome' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'category' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'overallCondition' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'allowedActions' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'code' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'permission' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'maximumTemperatureC',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: {
                                kind: 'Name',
                                value: 'prohibitedActions',
                              },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'code' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'permission' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'maximumTemperatureC',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'uncertainties' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'conflicts' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'id' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'fieldPath' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'severity' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'explanationKey',
                                    },
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
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'observations' },
                  selectionSet: {
                    kind: 'SelectionSet',
                    selections: [
                      { kind: 'Field', name: { kind: 'Name', value: 'id' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'observationType' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'stability' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'authority' },
                      },
                      { kind: 'Field', name: { kind: 'Name', value: 'value' } },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'evidenceIds' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'confidence' },
                      },
                      {
                        kind: 'Field',
                        name: { kind: 'Name', value: 'analysisRevisionId' },
                      },
                      {
                        kind: 'Field',
                        name: {
                          kind: 'Name',
                          value: 'supersedesObservationId',
                        },
                      },
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
                { kind: 'Field', name: { kind: 'Name', value: 'viewpoint' } },
                { kind: 'Field', name: { kind: 'Name', value: 'labelScope' } },
                {
                  kind: 'Field',
                  name: { kind: 'Name', value: 'qualityState' },
                },
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
                        name: { kind: 'Name', value: 'result' },
                        selectionSet: {
                          kind: 'SelectionSet',
                          selections: [
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'schemaVersion' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'outcome' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'warnings' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'category' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'subtype' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'colors' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'pattern' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'features' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'overallCondition' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'issues' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'id' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'kind' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'severity' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'location' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'observedDescription',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'confidence' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'suspectedCauses',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'confirmedCause',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'causeState' },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'visibleLabelText' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'imageId' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'text' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'language' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'confidence' },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'materials' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'material' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'percentage' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'confidence' },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'labelWarnings' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'allowedActions' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'code' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'permission' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'maximumTemperatureC',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'process' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'reasonKey' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'professionalOnly',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: {
                                kind: 'Name',
                                value: 'prohibitedActions',
                              },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'code' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'permission' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'maximumTemperatureC',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'process' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'reasonKey' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'professionalOnly',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'unknownActions' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'code' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'permission' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'maximumTemperatureC',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'process' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'reasonKey' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'professionalOnly',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: {
                                kind: 'Name',
                                value: 'professionalOnlyActions',
                              },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'code' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'permission' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'maximumTemperatureC',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'process' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'reasonKey' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'professionalOnly',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'uncertainties' },
                            },
                            {
                              kind: 'Field',
                              name: {
                                kind: 'Name',
                                value: 'clearerImageRequests',
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'conflicts' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'id' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'fieldPath' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'selectedValue',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'resolutionCode',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'explanationKey',
                                    },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'severity' },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'branches' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'branch' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'status' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'schemaVersion',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'stainSteps' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'claimId' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'status' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'text' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'actionCode' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: {
                                      kind: 'Name',
                                      value: 'violationCodes',
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'historyEventIds' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'preferenceSource' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'versions' },
                              selectionSet: {
                                kind: 'SelectionSet',
                                selections: [
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'name' },
                                  },
                                  {
                                    kind: 'Field',
                                    name: { kind: 'Name', value: 'value' },
                                  },
                                ],
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'productBarcode' },
                            },
                            {
                              kind: 'Field',
                              name: {
                                kind: 'Name',
                                value: 'productLookupStatus',
                              },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'productSource' },
                            },
                            {
                              kind: 'Field',
                              name: { kind: 'Name', value: 'productFacts' },
                            },
                          ],
                        },
                      },
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
