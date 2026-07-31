/* eslint-disable */
import * as types from './graphql';
import { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';

/**
 * Map of all GraphQL operations in the project.
 *
 * This map has several performance disadvantages:
 * 1. It is not tree-shakeable, so it will include all operations in the project.
 * 2. It is not minifiable, so the string of a GraphQL query will be multiple times inside the bundle.
 * 3. It does not support dead code elimination, so it will add unused operations.
 *
 * Therefore it is highly recommended to use the babel or swc plugin for production.
 * Learn more about it here: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client#reducing-bundle-size
 */
type Documents = {
  'query ScanMessages($scanId: UUID!, $first: Int!, $after: String) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}': typeof types.ScanMessagesDocument;
  'query GarmentDetail($garmentId: UUID!, $first: Int!, $after: String, $language: String!) {\n  garmentDetail(id: $garmentId, first: $first, after: $after, language: $language) {\n    id\n    displayName\n    identifiers\n    thumbnailScanId\n    thumbnailImageId\n    lastAnalysisAt\n    analysedBefore\n    cleanedBefore\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    activeResult {\n      id\n      status\n      language\n      data\n    }\n    analyses {\n      items {\n        scanId\n        status\n        createdAt\n        resultAvailable\n        thumbnailScanId\n        thumbnailImageId\n      }\n      pageInfo {\n        nextCursor\n      }\n    }\n    serviceEvents {\n      id\n      kind\n      note\n      createdAt\n    }\n  }\n}': typeof types.GarmentDetailDocument;
  'query GarmentHistory($first: Int!, $after: String) {\n  garmentHistory(first: $first, after: $after) {\n    items {\n      id\n      identifiers\n      thumbnailUrl\n      thumbnailScanId\n      thumbnailImageId\n      lastAnalysisAt\n      analysedBefore\n      cleanedBefore\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}': typeof types.GarmentHistoryDocument;
  'query ScanImageMetadata($scanId: UUID!) {\n  imageMetadata(scanId: $scanId) {\n    id\n    role\n    displayOrder\n    width\n    height\n  }\n}': typeof types.ScanImageMetadataDocument;
  'query ResultComposite($scanId: UUID!, $language: String!) {\n  scanResult(scanId: $scanId, language: $language) {\n    scan {\n      id\n      status\n      requestedLanguage\n      progressPercent\n      analysisStage\n      errorCode\n      garmentId\n      createdAt\n    }\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    result {\n      id\n      status\n      language\n      data\n    }\n    garment {\n      id\n      displayName\n      archivedAt\n      activeResultId\n      createdAt\n    }\n    identityCandidates {\n      id\n      garmentId\n      thumbnailScanId\n      thumbnailImageId\n      classification\n      reasons\n      status\n    }\n  }\n}': typeof types.ResultCompositeDocument;
  'fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}': typeof types.ScanSummaryFragmentDoc;
};
const documents: Documents = {
  'query ScanMessages($scanId: UUID!, $first: Int!, $after: String) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}':
    types.ScanMessagesDocument,
  'query GarmentDetail($garmentId: UUID!, $first: Int!, $after: String, $language: String!) {\n  garmentDetail(id: $garmentId, first: $first, after: $after, language: $language) {\n    id\n    displayName\n    identifiers\n    thumbnailScanId\n    thumbnailImageId\n    lastAnalysisAt\n    analysedBefore\n    cleanedBefore\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    activeResult {\n      id\n      status\n      language\n      data\n    }\n    analyses {\n      items {\n        scanId\n        status\n        createdAt\n        resultAvailable\n        thumbnailScanId\n        thumbnailImageId\n      }\n      pageInfo {\n        nextCursor\n      }\n    }\n    serviceEvents {\n      id\n      kind\n      note\n      createdAt\n    }\n  }\n}':
    types.GarmentDetailDocument,
  'query GarmentHistory($first: Int!, $after: String) {\n  garmentHistory(first: $first, after: $after) {\n    items {\n      id\n      identifiers\n      thumbnailUrl\n      thumbnailScanId\n      thumbnailImageId\n      lastAnalysisAt\n      analysedBefore\n      cleanedBefore\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}':
    types.GarmentHistoryDocument,
  'query ScanImageMetadata($scanId: UUID!) {\n  imageMetadata(scanId: $scanId) {\n    id\n    role\n    displayOrder\n    width\n    height\n  }\n}':
    types.ScanImageMetadataDocument,
  'query ResultComposite($scanId: UUID!, $language: String!) {\n  scanResult(scanId: $scanId, language: $language) {\n    scan {\n      id\n      status\n      requestedLanguage\n      progressPercent\n      analysisStage\n      errorCode\n      garmentId\n      createdAt\n    }\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    result {\n      id\n      status\n      language\n      data\n    }\n    garment {\n      id\n      displayName\n      archivedAt\n      activeResultId\n      createdAt\n    }\n    identityCandidates {\n      id\n      garmentId\n      thumbnailScanId\n      thumbnailImageId\n      classification\n      reasons\n      status\n    }\n  }\n}':
    types.ResultCompositeDocument,
  'fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}':
    types.ScanSummaryFragmentDoc,
};

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 *
 *
 * @example
 * ```ts
 * const query = graphql(`query GetUser($id: ID!) { user(id: $id) { name } }`);
 * ```
 *
 * The query argument is unknown!
 * Please regenerate the types.
 */
export function graphql(source: string): unknown;

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query ScanMessages($scanId: UUID!, $first: Int!, $after: String) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}',
): (typeof documents)['query ScanMessages($scanId: UUID!, $first: Int!, $after: String) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}'];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query GarmentDetail($garmentId: UUID!, $first: Int!, $after: String, $language: String!) {\n  garmentDetail(id: $garmentId, first: $first, after: $after, language: $language) {\n    id\n    displayName\n    identifiers\n    thumbnailScanId\n    thumbnailImageId\n    lastAnalysisAt\n    analysedBefore\n    cleanedBefore\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    activeResult {\n      id\n      status\n      language\n      data\n    }\n    analyses {\n      items {\n        scanId\n        status\n        createdAt\n        resultAvailable\n        thumbnailScanId\n        thumbnailImageId\n      }\n      pageInfo {\n        nextCursor\n      }\n    }\n    serviceEvents {\n      id\n      kind\n      note\n      createdAt\n    }\n  }\n}',
): (typeof documents)['query GarmentDetail($garmentId: UUID!, $first: Int!, $after: String, $language: String!) {\n  garmentDetail(id: $garmentId, first: $first, after: $after, language: $language) {\n    id\n    displayName\n    identifiers\n    thumbnailScanId\n    thumbnailImageId\n    lastAnalysisAt\n    analysedBefore\n    cleanedBefore\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    activeResult {\n      id\n      status\n      language\n      data\n    }\n    analyses {\n      items {\n        scanId\n        status\n        createdAt\n        resultAvailable\n        thumbnailScanId\n        thumbnailImageId\n      }\n      pageInfo {\n        nextCursor\n      }\n    }\n    serviceEvents {\n      id\n      kind\n      note\n      createdAt\n    }\n  }\n}'];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query GarmentHistory($first: Int!, $after: String) {\n  garmentHistory(first: $first, after: $after) {\n    items {\n      id\n      identifiers\n      thumbnailUrl\n      thumbnailScanId\n      thumbnailImageId\n      lastAnalysisAt\n      analysedBefore\n      cleanedBefore\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}',
): (typeof documents)['query GarmentHistory($first: Int!, $after: String) {\n  garmentHistory(first: $first, after: $after) {\n    items {\n      id\n      identifiers\n      thumbnailUrl\n      thumbnailScanId\n      thumbnailImageId\n      lastAnalysisAt\n      analysedBefore\n      cleanedBefore\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}'];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query ScanImageMetadata($scanId: UUID!) {\n  imageMetadata(scanId: $scanId) {\n    id\n    role\n    displayOrder\n    width\n    height\n  }\n}',
): (typeof documents)['query ScanImageMetadata($scanId: UUID!) {\n  imageMetadata(scanId: $scanId) {\n    id\n    role\n    displayOrder\n    width\n    height\n  }\n}'];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query ResultComposite($scanId: UUID!, $language: String!) {\n  scanResult(scanId: $scanId, language: $language) {\n    scan {\n      id\n      status\n      requestedLanguage\n      progressPercent\n      analysisStage\n      errorCode\n      garmentId\n      createdAt\n    }\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    result {\n      id\n      status\n      language\n      data\n    }\n    garment {\n      id\n      displayName\n      archivedAt\n      activeResultId\n      createdAt\n    }\n    identityCandidates {\n      id\n      garmentId\n      thumbnailScanId\n      thumbnailImageId\n      classification\n      reasons\n      status\n    }\n  }\n}',
): (typeof documents)['query ResultComposite($scanId: UUID!, $language: String!) {\n  scanResult(scanId: $scanId, language: $language) {\n    scan {\n      id\n      status\n      requestedLanguage\n      progressPercent\n      analysisStage\n      errorCode\n      garmentId\n      createdAt\n    }\n    activeAnalysis {\n      id\n      scanId\n      status\n      revisionNumber\n      createdAt\n    }\n    result {\n      id\n      status\n      language\n      data\n    }\n    garment {\n      id\n      displayName\n      archivedAt\n      activeResultId\n      createdAt\n    }\n    identityCandidates {\n      id\n      garmentId\n      thumbnailScanId\n      thumbnailImageId\n      classification\n      reasons\n      status\n    }\n  }\n}'];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}',
): (typeof documents)['fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}'];

export function graphql(source: string) {
  return (documents as any)[source] ?? {};
}

export type DocumentType<TDocumentNode extends DocumentNode<any, any>> =
  TDocumentNode extends DocumentNode<infer TType, any> ? TType : never;
