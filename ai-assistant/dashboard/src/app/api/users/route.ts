import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongodb";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const search = searchParams.get("search") || "";

    const db = await getDb();

    let query = {};
    if (search) {
      const searchRegex = new RegExp(search, "i");
      
      // Check if search query is a number (Telegram ID)
      const searchNum = parseInt(search, 10);
      if (!isNaN(searchNum)) {
        query = {
          $or: [
            { telegram_id: searchNum },
            { username: searchRegex },
            { first_name: searchRegex },
            { last_name: searchRegex },
          ]
        };
      } else {
        query = {
          $or: [
            { username: searchRegex },
            { first_name: searchRegex },
            { last_name: searchRegex },
          ]
        };
      }
    }

    const users = await db
      .collection("users")
      .find(query)
      .sort({ last_seen: -1 })
      .toArray();

    return NextResponse.json({
      success: true,
      users,
    });
  } catch (error: any) {
    console.error("Users API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch users: " + error.message },
      { status: 500 }
    );
  }
}
