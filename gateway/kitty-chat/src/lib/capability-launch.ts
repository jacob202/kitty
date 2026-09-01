export function composeSkillLaunchInput(existingDraft: string, skillName: string): string {
  const directive = `Use skill: ${skillName}\n\n`
  return existingDraft ? `${directive}${existingDraft}` : directive
}
