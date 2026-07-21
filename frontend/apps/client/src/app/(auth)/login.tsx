import type { ReactNode } from 'react';
import { AuthForm } from '../../components/AuthForm';
export default function Login(): ReactNode {
  return <AuthForm mode="login" />;
}
