import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;

  // Allow static assets, login page, and authentication API route
  if (
    path.startsWith("/_next") ||
    path.startsWith("/static") ||
    path.startsWith("/favicon.ico") ||
    path === "/login" ||
    path === "/api/auth"
  ) {
    return NextResponse.next();
  }

  const systemPasscode = process.env.DASHBOARD_PASSCODE || "admin123";
  const clientPasscode = request.cookies.get("dashboard_passcode")?.value;

  if (!clientPasscode || clientPasscode !== systemPasscode) {
    // If request is to an API route, return 401 Unauthorized
    if (path.startsWith("/api/")) {
      return new NextResponse(
        JSON.stringify({ error: "Unauthorized. Passcode required." }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      );
    }

    // For web page requests, redirect to login page
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

// Apply middleware to all routes except static files
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (auth api)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
