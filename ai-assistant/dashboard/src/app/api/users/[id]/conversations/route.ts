import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongodb";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const userId = parseInt(id, 10);

    if (isNaN(userId)) {
      return NextResponse.json(
        { error: "Invalid Telegram ID" },
        { status: 400 }
      );
    }

    const db = await getDb();

    // Fetch all conversations for the user sorted by last updated timestamp
    const conversations = await db
      .collection("conversations")
      .find({ user_id: userId })
      .sort({ updated_at: -1 })
      .toArray();

    return NextResponse.json({
      success: true,
      conversations,
    });
  } catch (error: any) {
    console.error("Conversations API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch conversations: " + error.message },
      { status: 500 }
    );
  }
}
