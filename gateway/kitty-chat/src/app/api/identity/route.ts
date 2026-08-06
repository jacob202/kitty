import { NextResponse } from "next/server";

/** Stable, non-secret identity used by rollback/doctor checks.
 *
 * A generic HTTP 200 is not proof that Kitty owns the configured UI port; a
 * different development server could already be listening there. Keep this
 * endpoint deliberately tiny and independent of backend availability so the
 * operator can distinguish the Kitty shell from an unrelated process.
 */
export async function GET() {
  return NextResponse.json({
    product: "kitty",
    surface: "nextjs",
    schema_version: 1,
  });
}
