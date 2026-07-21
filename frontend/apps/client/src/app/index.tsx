import type { ReactNode } from 'react';
import { Redirect } from 'expo-router';
import { useSession } from '../auth/session';
export default function Home(): ReactNode {
  const { token } = useSession();
  return <Redirect href={token ? '/scan' : '/login'} />;
}
