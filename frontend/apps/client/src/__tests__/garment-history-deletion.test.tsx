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
  useQuery: jest.fn(() => ({
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
          {
            analysedBefore: true,
            cleanedBefore: false,
            id: '63b5399e-6c88-47fa-a171-1dc596db4c50',
            identifiers: ['FA-EXAMPLE-2'],
            lastAnalysisAt: null,
            thumbnailUrl: null,
            thumbnailScanId: null,
            thumbnailImageId: null,
          },
        ],
      },
    },
    error: undefined,
    loading: false,
  })),
}));

const mockApolloQuery = jest.requireMock('@apollo/client')
  .useQuery as jest.Mock;

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
    mutate: (garmentIds: string[]) => {
      mockMutate(garmentIds);
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

jest.mock('expo-router', () => ({
  router: { push: jest.fn() },
  useFocusEffect: jest.fn(),
}));
jest.mock('@expo/vector-icons/Feather', () => 'Feather');

beforeEach(() => {
  mockMutate.mockClear();
  mockPreview.mockClear();
  mockApolloQuery.mockClear();
});

test('history list closes the dialog after confirmed garment deletion', async () => {
  const screen = await render(<CustomerHistory />);

  await fireEvent.press(screen.getAllByLabelText('deleteGarment')[0]!);

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

test('history list confirms and deletes multiple selected garment histories', async () => {
  const screen = await render(<CustomerHistory />);

  await fireEvent.press(screen.getByLabelText('selectGarments'));
  const garmentSelectors = screen.getAllByLabelText('selectGarmentForDeletion');
  expect(garmentSelectors).toHaveLength(2);
  await fireEvent.press(garmentSelectors[0]!);
  await fireEvent.press(garmentSelectors[1]!);

  expect(screen.getByText('selectedGarmentsCount')).toBeTruthy();
  await fireEvent.press(screen.getByLabelText('deleteSelectedGarments'));
  expect(screen.getByText('deleteGarmentsConfirmDescription')).toBeTruthy();

  await fireEvent.press(screen.getByLabelText('deleteGarmentsConfirmAction'));
  expect(mockMutate).toHaveBeenLastCalledWith([
    '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
    '63b5399e-6c88-47fa-a171-1dc596db4c50',
  ]);
});

test('history list requests a canonical network snapshot', async () => {
  await render(<CustomerHistory />);

  expect(mockApolloQuery).toHaveBeenLastCalledWith(
    {},
    expect.objectContaining({
      fetchPolicy: 'network-only',
      variables: { after: null, first: 20 },
    }),
  );
});
