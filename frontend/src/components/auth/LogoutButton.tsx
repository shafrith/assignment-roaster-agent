import { Button, type ButtonProps } from '@chakra-ui/react';
import { useState } from 'react';
import { FiLogOut } from 'react-icons/fi';
import { useAuth } from '../../hooks/useAuth';

export type LogoutButtonProps = Omit<ButtonProps, 'onClick' | 'isLoading'>;

export function LogoutButton({ children, ...rest }: LogoutButtonProps) {
  const { logout } = useAuth();
  const [busy, setBusy] = useState<boolean>(false);

  const handleClick = async (): Promise<void> => {
    setBusy(true);
    try {
      await logout();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button variant="outline" leftIcon={<FiLogOut />} isLoading={busy} onClick={() => void handleClick()} {...rest}>
      {children ?? 'Logout'}
    </Button>
  );
}

export default LogoutButton;
