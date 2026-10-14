import { Button, type ButtonProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';

export interface PrimaryLinkButtonProps extends Omit<ButtonProps, 'children' | 'as'> {
  to: string;
  children: ReactNode;
}

/** PrimaryButton look, rendered as a react-router Link. */
export function PrimaryLinkButton({ to, children, ...rest }: PrimaryLinkButtonProps) {
  return (
    <Button as={RouterLink} to={to} size="lg" px={8} colorScheme="brand" {...rest}>
      {children}
    </Button>
  );
}

export default PrimaryLinkButton;
