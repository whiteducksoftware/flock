/**
 * Type names without their module path: `SupportTicket`, not
 * `__main__.SupportTicket` (design principle 4). The full path belongs in
 * the tooltip.
 */

/** `__main__.SupportTicket` -> `SupportTicket`; `Decision[app.Route]` -> `Decision[Route]`. */
export function shortTypeName(typeName: string): string {
  return typeName.replace(/(?:[A-Za-z_][\w]*\.)+(?=[A-Za-z_][\w]*)/g, '');
}
