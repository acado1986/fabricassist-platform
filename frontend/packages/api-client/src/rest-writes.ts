import {
  addImageApiV1ScansScanIdImagesPost as addImage,
  addServiceEventApiV1GarmentsGarmentIdServiceEventsPost as addServiceEvent,
  approveReviewApiV1ReviewsReviewIdApprovePost as approveReview,
  assignReviewApiV1ReviewsReviewIdAssignPost as assignReview,
  cancelRunApiV1RunsRunIdCancelPost as cancelRun,
  completeUploadApiV1ScansScanIdUploadsCompletePost as completeUpload,
  confirmIdentityCandidateApiV1GarmentsIdentityCandidatesScanIdConfirmPost as confirmIdentity,
  confirmServiceEventApiV1ReviewsReviewIdServiceEventsPost as confirmServiceEvent,
  correctReviewApiV1ReviewsReviewIdCorrectionsPost as correctReview,
  createScanApiV1ScansPost as createScan,
  deleteGarmentApiV1GarmentsGarmentIdDelete as deleteGarment,
  deleteScanApiV1ScansScanIdDelete as deleteScan,
  invalidateLatestProductLookupApiV1ScansScanIdProductLookupInvalidatePost as invalidateProductLookup,
  loginApiV1AuthLoginPost as login,
  logoutApiV1AuthLogoutPost as logout,
  postMessageApiV1ScansScanIdMessagesPost as postMessage,
  productLookupApiV1ScansScanIdProductLookupPost as productLookup,
  refreshApiV1AuthRefreshPost as refresh,
  registerApiV1AuthRegisterPost as register,
  rejectIdentityCandidateApiV1GarmentsIdentityCandidatesScanIdRejectPost as rejectIdentity,
  removeImageApiV1ScansScanIdImagesImageIdDelete as removeImage,
  requestAnalysisApiV1ScansScanIdAnalysePost as requestAnalysis,
  retryRunApiV1RunsRunIdRetryPost as retryRun,
  startRunApiV1ScansScanIdRunsPost as startRun,
  submitFeedbackApiV1ScansScanIdFeedbackPost as submitFeedback,
} from './generated/sdk.gen';
import type { Client } from './generated/client';

export type CacheEffect =
  | { kind: 'refetch'; queries: readonly string[] }
  | {
      kind: 'evict-and-refetch';
      entity: 'GarmentType' | 'ScanType';
      queries: readonly string[];
    }
  | { kind: 'clear-authenticated-cache' }
  | { kind: 'noGraphQLEffect'; reason: string };

export const REST_WRITE_REGISTRY = {
  login: { kind: 'clear-authenticated-cache' },
  register: { kind: 'clear-authenticated-cache' },
  refresh: {
    kind: 'noGraphQLEffect',
    reason: 'Refresh only rotates session credentials.',
  },
  logout: { kind: 'clear-authenticated-cache' },
  createScan: { kind: 'refetch', queries: ['GarmentHistory'] },
  addImage: { kind: 'refetch', queries: ['ScanImageMetadata'] },
  removeImage: {
    kind: 'refetch',
    queries: ['ScanImageMetadata', 'ResultComposite'],
  },
  completeUpload: {
    kind: 'refetch',
    queries: ['ScanImageMetadata', 'ResultComposite'],
  },
  requestAnalysis: { kind: 'refetch', queries: ['ResultComposite'] },
  startRun: {
    kind: 'refetch',
    queries: ['ResultComposite'],
  },
  retryRun: {
    kind: 'refetch',
    queries: ['ResultComposite'],
  },
  cancelRun: {
    kind: 'refetch',
    queries: ['ResultComposite'],
  },
  productLookup: { kind: 'refetch', queries: ['ResultComposite'] },
  invalidateProductLookup: { kind: 'refetch', queries: ['ResultComposite'] },
  postMessage: { kind: 'refetch', queries: ['ScanMessages'] },
  confirmIdentity: {
    kind: 'refetch',
    queries: ['ResultComposite', 'GarmentDetail', 'GarmentHistory'],
  },
  rejectIdentity: { kind: 'refetch', queries: ['ResultComposite'] },
  submitFeedback: { kind: 'refetch', queries: ['ResultComposite'] },
  deleteScan: {
    kind: 'evict-and-refetch',
    entity: 'ScanType',
    queries: ['ResultComposite'],
  },
  deleteGarment: {
    kind: 'evict-and-refetch',
    entity: 'GarmentType',
    queries: ['GarmentHistory', 'GarmentDetail'],
  },
  addServiceEvent: {
    kind: 'refetch',
    queries: ['GarmentDetail', 'GarmentHistory'],
  },
  assignReview: {
    kind: 'refetch',
    queries: ['ReviewQueue', 'ResultComposite'],
  },
  correctReview: {
    kind: 'refetch',
    queries: ['ReviewQueue', 'ResultComposite'],
  },
  approveReview: {
    kind: 'refetch',
    queries: ['ReviewQueue', 'ResultComposite'],
  },
  confirmServiceEvent: {
    kind: 'refetch',
    queries: ['ReviewQueue', 'GarmentDetail', 'GarmentHistory'],
  },
} as const satisfies Record<string, CacheEffect>;

export type RestWriteOperation = keyof typeof REST_WRITE_REGISTRY;
export type RestWriteEffectHandler = (
  operation: RestWriteOperation,
  effect: CacheEffect,
) => Promise<void> | void;

type RestWriteResult = {
  data?: unknown;
  error?: unknown;
  response?: Response;
};

type GeneratedOptions = Record<string, unknown>;

function withClient(options: unknown, client: Client): GeneratedOptions {
  return {
    ...(options && typeof options === 'object' ? options : {}),
    client,
  };
}

export function createRestWriteClient({
  client,
  applyEffect,
}: {
  client: Client;
  applyEffect: RestWriteEffectHandler;
}) {
  async function execute(
    operation: RestWriteOperation,
    request: () => Promise<unknown>,
  ): Promise<unknown> {
    const result = await request();
    const restResult = result as RestWriteResult;
    const successful =
      restResult.error === undefined &&
      (restResult.response?.ok ?? restResult.data !== undefined);
    if (successful)
      await applyEffect(operation, REST_WRITE_REGISTRY[operation]);
    return result;
  }

  return {
    login: (options: Parameters<typeof login>[0]) =>
      execute('login', () =>
        login(withClient(options, client) as Parameters<typeof login>[0]),
      ) as ReturnType<typeof login>,
    register: (options: Parameters<typeof register>[0]) =>
      execute('register', () =>
        register(withClient(options, client) as Parameters<typeof register>[0]),
      ) as ReturnType<typeof register>,
    refresh: (options?: Parameters<typeof refresh>[0]) =>
      execute('refresh', () =>
        refresh(withClient(options, client) as Parameters<typeof refresh>[0]),
      ) as ReturnType<typeof refresh>,
    logout: (options?: Parameters<typeof logout>[0]) =>
      execute('logout', () =>
        logout(withClient(options, client) as Parameters<typeof logout>[0]),
      ) as ReturnType<typeof logout>,
    createScan: (options: Parameters<typeof createScan>[0]) =>
      execute('createScan', () =>
        createScan(
          withClient(options, client) as Parameters<typeof createScan>[0],
        ),
      ) as ReturnType<typeof createScan>,
    addImage: (options: Parameters<typeof addImage>[0]) =>
      execute('addImage', () =>
        addImage(withClient(options, client) as Parameters<typeof addImage>[0]),
      ) as ReturnType<typeof addImage>,
    removeImage: (options: Parameters<typeof removeImage>[0]) =>
      execute('removeImage', () =>
        removeImage(
          withClient(options, client) as Parameters<typeof removeImage>[0],
        ),
      ) as ReturnType<typeof removeImage>,
    completeUpload: (options: Parameters<typeof completeUpload>[0]) =>
      execute('completeUpload', () =>
        completeUpload(
          withClient(options, client) as Parameters<typeof completeUpload>[0],
        ),
      ) as ReturnType<typeof completeUpload>,
    requestAnalysis: (options: Parameters<typeof requestAnalysis>[0]) =>
      execute('requestAnalysis', () =>
        requestAnalysis(
          withClient(options, client) as Parameters<typeof requestAnalysis>[0],
        ),
      ) as ReturnType<typeof requestAnalysis>,
    startRun: (options: Parameters<typeof startRun>[0]) =>
      execute('startRun', () =>
        startRun(withClient(options, client) as Parameters<typeof startRun>[0]),
      ) as ReturnType<typeof startRun>,
    retryRun: (options: Parameters<typeof retryRun>[0]) =>
      execute('retryRun', () =>
        retryRun(withClient(options, client) as Parameters<typeof retryRun>[0]),
      ) as ReturnType<typeof retryRun>,
    cancelRun: (options: Parameters<typeof cancelRun>[0]) =>
      execute('cancelRun', () =>
        cancelRun(
          withClient(options, client) as Parameters<typeof cancelRun>[0],
        ),
      ) as ReturnType<typeof cancelRun>,
    productLookup: (options: Parameters<typeof productLookup>[0]) =>
      execute('productLookup', () =>
        productLookup(
          withClient(options, client) as Parameters<typeof productLookup>[0],
        ),
      ) as ReturnType<typeof productLookup>,
    invalidateProductLookup: (
      options: Parameters<typeof invalidateProductLookup>[0],
    ) =>
      execute('invalidateProductLookup', () =>
        invalidateProductLookup(
          withClient(options, client) as Parameters<
            typeof invalidateProductLookup
          >[0],
        ),
      ) as ReturnType<typeof invalidateProductLookup>,
    postMessage: (options: Parameters<typeof postMessage>[0]) =>
      execute('postMessage', () =>
        postMessage(
          withClient(options, client) as Parameters<typeof postMessage>[0],
        ),
      ) as ReturnType<typeof postMessage>,
    confirmIdentity: (options: Parameters<typeof confirmIdentity>[0]) =>
      execute('confirmIdentity', () =>
        confirmIdentity(
          withClient(options, client) as Parameters<typeof confirmIdentity>[0],
        ),
      ) as ReturnType<typeof confirmIdentity>,
    rejectIdentity: (options: Parameters<typeof rejectIdentity>[0]) =>
      execute('rejectIdentity', () =>
        rejectIdentity(
          withClient(options, client) as Parameters<typeof rejectIdentity>[0],
        ),
      ) as ReturnType<typeof rejectIdentity>,
    submitFeedback: (options: Parameters<typeof submitFeedback>[0]) =>
      execute('submitFeedback', () =>
        submitFeedback(
          withClient(options, client) as Parameters<typeof submitFeedback>[0],
        ),
      ) as ReturnType<typeof submitFeedback>,
    deleteScan: (options: Parameters<typeof deleteScan>[0]) =>
      execute('deleteScan', () =>
        deleteScan(
          withClient(options, client) as Parameters<typeof deleteScan>[0],
        ),
      ) as ReturnType<typeof deleteScan>,
    deleteGarment: (options: Parameters<typeof deleteGarment>[0]) =>
      execute('deleteGarment', () =>
        deleteGarment(
          withClient(options, client) as Parameters<typeof deleteGarment>[0],
        ),
      ) as ReturnType<typeof deleteGarment>,
    addServiceEvent: (options: Parameters<typeof addServiceEvent>[0]) =>
      execute('addServiceEvent', () =>
        addServiceEvent(
          withClient(options, client) as Parameters<typeof addServiceEvent>[0],
        ),
      ) as ReturnType<typeof addServiceEvent>,
    assignReview: (options: Parameters<typeof assignReview>[0]) =>
      execute('assignReview', () =>
        assignReview(
          withClient(options, client) as Parameters<typeof assignReview>[0],
        ),
      ) as ReturnType<typeof assignReview>,
    correctReview: (options: Parameters<typeof correctReview>[0]) =>
      execute('correctReview', () =>
        correctReview(
          withClient(options, client) as Parameters<typeof correctReview>[0],
        ),
      ) as ReturnType<typeof correctReview>,
    approveReview: (options: Parameters<typeof approveReview>[0]) =>
      execute('approveReview', () =>
        approveReview(
          withClient(options, client) as Parameters<typeof approveReview>[0],
        ),
      ) as ReturnType<typeof approveReview>,
    confirmServiceEvent: (options: Parameters<typeof confirmServiceEvent>[0]) =>
      execute('confirmServiceEvent', () =>
        confirmServiceEvent(
          withClient(options, client) as Parameters<
            typeof confirmServiceEvent
          >[0],
        ),
      ) as ReturnType<typeof confirmServiceEvent>,
  };
}
