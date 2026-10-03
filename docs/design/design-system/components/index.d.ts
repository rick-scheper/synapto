import type * as React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'md' | 'sm'; icon?: React.ReactNode }
export declare function Button(props: ButtonProps): React.ReactElement;

export interface BadgeProps { tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'danger'; children?: React.ReactNode }
export declare function Badge(props: BadgeProps): React.ReactElement;

export interface TabsProps { items: Array<string | { id: string; label: string; count?: number }>; value: string; onChange?: (id: string) => void }
export declare function Tabs(props: TabsProps): React.ReactElement;

export interface TextFieldProps { label?: string; value?: string; defaultValue?: string; onChange?: React.ChangeEventHandler<HTMLInputElement>; placeholder?: string; hint?: string; error?: string; mono?: boolean; disabled?: boolean }
export declare function TextField(props: TextFieldProps): React.ReactElement;

export interface ProgressRingProps { value: number; size?: number; stroke?: number; showLabel?: boolean }
export declare function ProgressRing(props: ProgressRingProps): React.ReactElement;

export interface LessonCardProps { title: string; summary?: string; date?: string; difficulty?: string; concepts?: string[]; progress?: number; stale?: boolean; repo?: string }
export declare function LessonCard(props: LessonCardProps): React.ReactElement;

export interface CalloutProps { tone?: 'info' | 'success' | 'warning' | 'danger'; title?: string; children?: React.ReactNode; action?: React.ReactNode }
export declare function Callout(props: CalloutProps): React.ReactElement;

export interface CodeCellProps { code: string; role?: 'setup' | 'function' | 'demo'; fn?: string; sourceRef?: string; status?: 'idle' | 'running' | 'done' | 'error'; execCount?: number; output?: string; time?: string }
export declare function CodeCell(props: CodeCellProps): React.ReactElement;

export interface QuizOptionProps { optionId: string; children?: React.ReactNode; state?: 'idle' | 'selected' | 'correct' | 'wrong'; onClick?: () => void; disabled?: boolean }
export declare function QuizOption(props: QuizOptionProps): React.ReactElement;

export interface TestResultProps { tests: Array<{ name: string; status: 'passed' | 'failed'; message?: string }> }
export declare function TestResult(props: TestResultProps): React.ReactElement;

export interface DecisionCardProps { title: string; context?: string; options: Array<{ id: string; label: string }>; chosen: string; why?: string; tradeoffs?: string }
export declare function DecisionCard(props: DecisionCardProps): React.ReactElement;

declare global { interface Window { Synapto: { Button: typeof Button; Badge: typeof Badge; Tabs: typeof Tabs; TextField: typeof TextField; ProgressRing: typeof ProgressRing; LessonCard: typeof LessonCard; Callout: typeof Callout; CodeCell: typeof CodeCell; QuizOption: typeof QuizOption; TestResult: typeof TestResult; DecisionCard: typeof DecisionCard } } }
