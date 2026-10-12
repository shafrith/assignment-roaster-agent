import { Box, Button, Stack } from '@chakra-ui/react';
import { motion, type MotionProps } from 'framer-motion';

/**
 * Chakra + Framer Motion components.
 * Chakra prop types collide with motion's (onAnimationStart, onDrag, transition, style...),
 * so component props should be built with `WithoutMotion<ChakraProps>` + motion props.
 */
export type WithoutMotion<P> = Omit<P, keyof MotionProps>;

export const MotionBox = motion(Box);
export const MotionButton = motion(Button);
export const MotionStack = motion(Stack);
