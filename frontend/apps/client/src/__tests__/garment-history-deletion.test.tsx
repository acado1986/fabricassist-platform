import type { ReactNode } from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import CustomerHistory from '../app/(customer)/history';

const mockMutate = jest.fn();

jest.mock('../auth/session', () => {
  const apiClient = {};
  return {
    useSession: () => ({
      apiClient,
      restWrites: {
        deleteGarment: jest
          .fn()
          .mockResolvedValue({ data: { status: 'deleted' } }),
      },
      token: 'access-token',
    }),
  };
});

jest.mock('@fabricassist/api-client', () => ({
  GarmentHistoryDocument: {},
  imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet: jest
    .fn()
    .mockResolvedValue({ data: { url: 'https://preview.example.test/image' } }),
}));

const mockPreview = jest.requireMock('@fabricassist/api-client')
  .imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet as jest.Mock;

jest.mock('@apollo/client', () => ({
  useQuery: () => ({
    data: {
      garmentHistory: {
        items: [
          {
            analysedBefore: true,
            cleanedBefore: false,
            id: '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
            identifiers: ['FA-EXAMPLE'],
            lastAnalysisAt: null,
            thumbnailUrl: null,
            thumbnailScanId: 'scan-1',
            thumbnailImageId: 'image-1',
          },
        ],
      },
    },
    error: undefined,
    loading: false,
  }),
}));

jest.mock('../i18n/TranslationProvider', () => ({
  useTranslation: () => ({
    locale: 'en',
    translate: (key: string) => key,
  }),
}));

jest.mock('../components/FoundationShell', () => ({
  FoundationShell: ({ children }: { children: ReactNode }) => children,
}));

jest.mock('@tanstack/react-query', () => ({
  useMutation: (options: { onSuccess: () => Promise<void> }) => ({
    isError: false,
    isPending: false,
    mutate: (garmentId: string) => {
      mockMutate(garmentId);
      void options.onSuccess();
    },
  }),
  useQuery: () => ({
    data: [
      {
        analysedBefore: true,
        cleanedBefore: false,
        id: '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
        identifiers: ['FA-EXAMPLE'],
        lastAnalysisAt: null,
        thumbnailUrl: null,
      },
    ],
    isError: false,
    isLoading: false,
  }),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock('expo-router', () => ({ router: { push: jest.fn() } }));
jest.mock('@expo/vector-icons/Feather', () => 'Feather');

test('history list closes the dialog after confirmed garment deletion', async () => {
  const screen = await render(<CustomerHistory />);

  await fireEvent.press(screen.getByLabelText('deleteGarment'));

  expect(mockMutate).not.toHaveBeenCalled();
  expect(screen.getByText('deleteGarmentConfirmDescription')).toBeTruthy();

  await fireEvent.press(screen.getByLabelText('deleteGarmentConfirmAction'));

  expect(mockMutate).toHaveBeenCalledWith([
    '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
  ]);
  await waitFor(() => {
    expect(screen.queryByText('deleteGarmentConfirmDescription')).toBeNull();
  });
});

test('history list loads garment thumbnails through the preview endpoint', async () => {
  const screen = await render(<CustomerHistory />);

  await waitFor(() => {
    expect(screen.getByLabelText('garmentThumbnail')).toBeTruthy();
  });
  expect(mockPreview).toHaveBeenCalledWith({
    client: expect.any(Object),
    path: { image_id: 'image-1', scan_id: 'scan-1' },
  });
});
