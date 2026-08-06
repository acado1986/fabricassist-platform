import type { ResultCompositeQuery } from '@fabricassist/api-client';

/** Generated contract-derived result model; no JSON casts or provider fields. */
export type GarmentAnalysisResultModel = NonNullable<
  NonNullable<ResultCompositeQuery['scanResult']>['result']
>['result'];
