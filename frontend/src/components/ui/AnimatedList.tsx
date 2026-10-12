import type { StackProps } from '@chakra-ui/react';
import type { Variants } from 'framer-motion';
import { Children, isValidElement, type ReactNode } from 'react';
import { MotionBox, MotionStack, type WithoutMotion } from '../../lib/motion';

const containerVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export interface AnimatedListProps extends WithoutMotion<Omit<StackProps, 'children'>> {
  children: ReactNode;
}

/** Stack whose children stagger in. Uses child keys when provided. */
export function AnimatedList({ children, spacing = 3, ...rest }: AnimatedListProps) {
  const items = Children.toArray(children);
  return (
    <MotionStack spacing={spacing} initial="hidden" animate="visible" variants={containerVariants} {...rest}>
      {items.map((child, index) => (
        <MotionBox key={isValidElement(child) && child.key !== null ? child.key : index} variants={itemVariants}>
          {child}
        </MotionBox>
      ))}
    </MotionStack>
  );
}

export default AnimatedList;
