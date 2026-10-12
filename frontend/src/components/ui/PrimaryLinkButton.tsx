import { Button, type ButtonProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';

export interface PrimaryLinkButtonProps extends Omit<ButtonProps, 'children' | 'as'> {
  to: string;
  children: ReactNode;
}

/** PrimaryButton look, rendered as a react-router Link (no Framer Motion so `as` typing stays intact). */
export function PrimaryLinkButton({ to, children, ...rest }: PrimaryLinkButtonProps) {
  return (
    <Button
      as={RouterLink}
      to={to}
      size="lg"
      px={8}
      color="white"
      bg="fire.500"
      transition="all 0.2s"
      _hover={{ bg: 'fire.600', transform: 'translateY(-2px)', color: 'white' }}
      _active={{ bg: 'fire.700', transform: 'scale(0.98)' }}
      {...rest}
    >
      {children}
    </Button>
  );
}

export default PrimaryLinkButton;
