import { expect, test } from '@playwright/test';

test('operator claims a review case and confirms the validated correction workflow', async ({
  page,
}) => {
  let assigned = false;
  let approved = false;
  await page.addInitScript(() =>
    sessionStorage.setItem('fabricassist_access_token', 'e2e-token'),
  );
  await page.route('**/api/v1/reviews', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        json: assigned ? [] : [{ id: 'review-1', status: 'open' }],
      });
      return;
    }
    await route.continue();
  });
  const reviewDetail = async (route: import('@playwright/test').Route) => {
    const url = route.request().url();
    if (url.endsWith('/assign')) {
      assigned = true;
      await route.fulfill({ json: { id: 'review-1', status: 'assigned' } });
      return;
    }
    if (url.endsWith('/approve')) {
      approved = true;
      await route.fulfill({ json: { id: 'review-1', status: 'approved' } });
      return;
    }
    if (url.endsWith('/corrections') || url.endsWith('/service-events')) {
      await route.fulfill({ json: { id: 'event-1', status: 'ok' } });
      return;
    }
    if (url.endsWith('/review-1')) {
      await route.fulfill({
        json: {
          id: 'review-1',
          status: 'assigned',
          dossier: {
            schema_version: 'garment-evidence-v1',
            observations: [],
            care_facts: [],
            uncertainties: [],
          },
          proposal: { cleaning: { method: 'unknown' } },
          validation: { outcome: 'needs_review' },
        },
      });
      return;
    }
    await route.continue();
  };
  await page.route('**/api/v1/reviews/review-1', reviewDetail);
  await page.route('**/api/v1/reviews/review-1/**', reviewDetail);
  await page.goto('/review');
  await page.getByRole('button', { name: /claim case/i }).click();
  await expect(page.getByText('Validate correction')).toBeVisible();
  await page
    .getByLabel('Correction reason')
    .fill('Confirmed a clearer photographed label.');
  await page.getByRole('button', { name: /validate correction/i }).click();
  await page.getByRole('button', { name: /approve result/i }).click();
  expect(approved).toBeTruthy();
});
