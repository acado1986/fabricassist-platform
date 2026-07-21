import type { ReactNode } from 'react';
import { AuthForm } from '../../components/AuthForm';
export default function Register(): ReactNode {
  return <AuthForm mode="register" />;
}
