import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongodb";
import { ObjectId } from "mongodb";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!ObjectId.isValid(id)) {
      return NextResponse.json(
        { error: "Invalid Conversation ID" },
        { status: 400 }
      );
    }

    const db = await getDb();
    const conversationId = new ObjectId(id);

    // Fetch messages for the conversation, ordered chronologically
    const messages = await db
      .collection("messages")
      .find({ conversation_id: conversationId })
      .sort({ created_at: 1 })
      .toArray();

    return NextResponse.json({
      success: true,
      messages,
    });
  } catch (error: any) {
    console.error("Messages API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch messages: " + error.message },
      { status: 500 }
    );
  }
}
