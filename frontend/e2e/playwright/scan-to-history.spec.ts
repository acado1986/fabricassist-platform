import { expect, test, type Route } from '@playwright/test';

const scanId = '11111111-1111-4111-8111-111111111111';
const imageId = '22222222-2222-4222-8222-222222222222';
const runId = '33333333-3333-4333-8333-333333333333';
const garmentId = '44444444-4444-4444-8444-444444444444';
const now = '2026-08-04T10:00:00Z';

async function fulfillGraphql(route: Route): Promise<void> {
  const request = route.request().postDataJSON() as { operationName?: string };
  if (request.operationName === 'GarmentHistory') {
    await route.fulfill({
      json: {
        data: {
          garmentHistory: {
            items: [
              {
                id: garmentId,
                identifiers: ['FA-E2E-001'],
                thumbnailUrl: null,
                thumbnailScanId: null,
                thumbnailImageId: null,
                lastAnalysisAt: now,
                analysedBefore: true,
                cleanedBefore: false,
              },
            ],
            pageInfo: { nextCursor: null },
          },
        },
      },
    });
    return;
  }
  await route.fulfill({
    json: {
      data: {
        scanResult: {
          scan: {
            id: scanId,
            status: 'completed',
            requestedLanguage: 'en',
            progressPercent: 100,
            analysisStage: 'completed',
            errorCode: null,
            garmentId,
            createdAt: now,
          },
          activeAnalysis: {
            id: '55555555-5555-4555-8555-555555555555',
            scanId,
            status: 'completed',
            revisionNumber: 1,
            createdAt: now,
          },
          result: {
            id: '66666666-6666-4666-8666-666666666666',
            status: 'passed',
            result: {
              schemaVersion: 'garment-analysis-result-v2',
              outcome: 'passed',
              warnings: [],
              category: 'shirt',
              subtype: null,
              colors: ['blue'],
              pattern: 'solid',
              features: [],
              overallCondition: 'good',
              issues: [],
              visibleLabelText: [],
              materials: [],
              labelWarnings: [],
              allowedActions: [],
              prohibitedActions: [],
              unknownActions: [],
              professionalOnlyActions: [],
              uncertainties: [],
              clearerImageRequests: [],
              conflicts: [],
              branches: [],
              stainSteps: [],
              historyEventIds: [],
              preferenceSource: 'none',
              versions: [
                {
                  name: 'cache_provenance',
                  value:
                    '{"garment_inspection":{"source":"postgres_exact","reused":true}}',
                },
              ],
              productBarcode: null,
              productLookupStatus: 'not_attempted',
              productSource: null,
              productFacts: null,
            },
          },
          garment: {
            id: garmentId,
            displayName: 'E2E shirt',
            archivedAt: null,
            activeResultId: '66666666-6666-4666-8666-666666666666',
            createdAt: now,
          },
          identityCandidates: [],
        },
      },
    },
  });
}

test('customer uploads a garment, sees the v2 result, and reaches garment history', async ({
  page,
}) => {
  await page.addInitScript(() =>
    sessionStorage.setItem(
      'fabricassist_access_token',
      'e2e.eyJleHAiOjQxMDI0NDQ4MDB9.signature',
    ),
  );
  await page.route('**/api/v1/graphql', fulfillGraphql);
  await page.route('**/api/v1/runs/*/events**', (route) => route.abort());
  await page.route('**/e2e-upload', (route) => route.fulfill({ status: 200 }));
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === 'POST' && path === '/api/v1/scans') {
      await route.fulfill({
        status: 201,
        json: { scan_id: scanId, status: 'uploading' },
      });
    } else if (
      request.method() === 'POST' &&
      path === `/api/v1/scans/${scanId}/images`
    ) {
      await route.fulfill({
        status: 201,
        json: {
          image_id: imageId,
          role: 'garment_overview',
          viewpoint: 'unknown',
          label_scope: 'unknown',
          url: 'http://localhost:8000/e2e-upload',
          headers: { 'Content-Type': 'image/jpeg' },
          expires_at: now,
        },
      });
    } else if (
      request.method() === 'POST' &&
      path === `/api/v1/scans/${scanId}/uploads/complete`
    ) {
      await route.fulfill({
        json: {
          scan_id: scanId,
          status: 'uploading',
          images_completed: 1,
          progress_percent: 0,
          analysis_stage: null,
          error_code: null,
          garment_id: null,
        },
      });
    } else if (
      request.method() === 'POST' &&
      path === `/api/v1/scans/${scanId}/runs`
    ) {
      await route.fulfill({
        status: 202,
        json: {
          run_id: runId,
          scan_id: scanId,
          status: 'queued',
          created_at: now,
          started_at: null,
          completed_at: null,
          error_code: null,
        },
      });
    } else {
      await route.fallback();
    }
  });

  await page.goto('/scan');
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Choose from library' }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: 'garment.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from('synthetic-garment-image'),
  });
  await expect(page.getByText('Photos: 1 of 8')).toBeVisible();
  await page.getByRole('button', { name: 'Analyse garment' }).click();

  await expect(page.getByRole('heading', { name: 'shirt' })).toBeVisible();
  await expect(page.getByText('Cache provenance')).toHaveCount(0);
  await page.getByRole('button', { name: 'Menu' }).click();
  await page.getByRole('menuitem', { name: 'History' }).click();
  await expect(page.getByText('FA-E2E-001')).toBeVisible();
  await expect(page.getByText(/Analysed before: Yes/)).toBeVisible();
});
