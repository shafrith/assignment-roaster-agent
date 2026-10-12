import { Button, type ButtonProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';

export interface GradientLinkButtonProps extends Omit<ButtonProps, 'children' | 'as'> {
  to: string;
  children: ReactNode;
}

/** GradientButton look, rendered as a react-router Link (no Framer Motion so `as` typing stays intact). */
export function GradientLinkButton({ to, children, ...rest }: GradientLinkButtonProps) {
  return (
    <Button
      as={RouterLink}
      to={to}
      size="lg"
      px={8}
      color="white"
      bgGradient="linear(to-r, fire.400, fire.600, red.600)"
      boxShadow="0 8px 24px -8px rgba(249, 89, 15, 0.6)"
      transition="all 0.2s"
      _hover={{
        bgGradient: 'linear(to-r, fire.300, fire.500, red.500)',
        boxShadow: '0 12px 32px -8px rgba(249, 89, 15, 0.8)',
        transform: 'translateY(-2px)',
        color: 'white',
      }}
      _active={{ bgGradient: 'linear(to-r, fire.500, fire.700, red.700)', transform: 'scale(0.98)' }}
      {...rest}
    >
      {children}
    </Button>
  );
}

export default GradientLinkButton;
