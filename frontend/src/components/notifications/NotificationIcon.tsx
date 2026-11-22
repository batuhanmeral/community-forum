import { AtSign, Bell, CheckCircle2, Coins, Flag, Mail, MessageSquare, Reply, UserPlus, type LucideIcon } from 'lucide-react';
import type { NotificationKind } from '@/features/notifications/format';

const ICONS: Record<NotificationKind, LucideIcon> = {
  comment: MessageSquare,
  reply: Reply,
  mention: AtSign,
  follow: UserPlus,
  message: Mail,
  mod: Flag,
  answer: CheckCircle2,
  bounty: Coins,
  other: Bell,
};

export function NotificationIcon({ kind }: { kind: NotificationKind }) {
  const Icon = ICONS[kind];
  return <Icon className="h-3.5 w-3.5" />;
}
