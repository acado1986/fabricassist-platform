/* eslint-disable */
import * as types from './graphql';

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
  'query ScanMessages($scanId: UUID!, $first: Int!, $after: UUID) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}': typeof types.ScanMessagesDocument;
  'query ScanHistory($first: Int!, $after: UUID) {\n  scans(first: $first, after: $after) {\n    items {\n      ...ScanSummary\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}': typeof types.ScanHistoryDocument;
  'query ScanRunRecovery($id: UUID!) {\n  scan(id: $id) {\n    ...ScanSummary\n  }\n}': typeof types.ScanRunRecoveryDocument;
  'fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}': typeof types.ScanSummaryFragmentDoc;
};
const documents: Documents = {
  'query ScanMessages($scanId: UUID!, $first: Int!, $after: UUID) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}':
    types.ScanMessagesDocument,
  'query ScanHistory($first: Int!, $after: UUID) {\n  scans(first: $first, after: $after) {\n    items {\n      ...ScanSummary\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}':
    types.ScanHistoryDocument,
  'query ScanRunRecovery($id: UUID!) {\n  scan(id: $id) {\n    ...ScanSummary\n  }\n}':
    types.ScanRunRecoveryDocument,
  'fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}':
    types.ScanSummaryFragmentDoc,
};

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query ScanMessages($scanId: UUID!, $first: Int!, $after: UUID) {\n  messages(scanId: $scanId, first: $first, after: $after) {\n    items {\n      id\n      role\n      status\n      text\n      createdAt\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}',
): typeof import('./graphql').ScanMessagesDocument;
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query ScanHistory($first: Int!, $after: UUID) {\n  scans(first: $first, after: $after) {\n    items {\n      ...ScanSummary\n    }\n    pageInfo {\n      nextCursor\n    }\n  }\n}',
): typeof import('./graphql').ScanHistoryDocument;
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'query ScanRunRecovery($id: UUID!) {\n  scan(id: $id) {\n    ...ScanSummary\n  }\n}',
): typeof import('./graphql').ScanRunRecoveryDocument;
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(
  source: 'fragment ScanSummary on ScanType {\n  id\n  status\n  requestedLanguage\n  progressPercent\n  analysisStage\n  errorCode\n  garmentId\n  createdAt\n}',
): typeof import('./graphql').ScanSummaryFragmentDoc;

export function graphql(source: string) {
  return (documents as any)[source] ?? {};
}
