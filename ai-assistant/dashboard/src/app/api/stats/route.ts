import { NextResponse } from "next/server";
import { getDb } from "@/lib/mongodb";

export async function GET() {
  try {
    const db = await getDb();

    // 1. User stats
    const totalUsers = await db.collection("users").countDocuments();

    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const activeUsers24h = await db.collection("users").countDocuments({
      last_seen: { $gte: oneDayAgo },
    });

    // 2. Message and token stats
    const totalMessages = await db.collection("messages").countDocuments();

    const tokenAgg = await db.collection("messages").aggregate([
      {
        $group: {
          _id: null,
          totalPromptTokens: { $sum: { $ifNull: ["$prompt_tokens", 0] } },
          totalCompletionTokens: { $sum: { $ifNull: ["$completion_tokens", 0] } },
          totalTokens: { $sum: { $ifNull: ["$total_tokens", 0] } },
          avgResponseTime: {
            $avg: {
              $cond: [
                {
                  $and: [
                    { $eq: ["$role", "assistant"] },
                    { $gt: [{ $ifNull: ["$response_time", 0] }, 0] }
                  ]
                },
                "$response_time",
                null
              ]
            }
          }
        }
      }
    ]).toArray();

    const tokenStats = tokenAgg[0] || {
      totalPromptTokens: 0,
      totalCompletionTokens: 0,
      totalTokens: 0,
      avgResponseTime: 0
    };

    // 3. Model breakdown
    const modelBreakdown = await db.collection("messages").aggregate([
      {
        $match: {
          role: "assistant",
          model: { $ne: null, $exists: true }
        }
      },
      {
        $group: {
          _id: "$model",
          count: { $sum: 1 }
        }
      },
      {
        $project: {
          model: "$_id",
          count: 1,
          _id: 0
        }
      },
      { $sort: { count: -1 } }
    ]).toArray();

    // 4. Daily chat volume (last 7 days)
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const dailyVolume = await db.collection("messages").aggregate([
      {
        $match: {
          created_at: { $gte: sevenDaysAgo }
        }
      },
      {
        $group: {
          _id: {
            $dateToString: { format: "%Y-%m-%d", date: "$created_at" }
          },
          messageCount: { $sum: 1 },
          tokenCount: { $sum: { $ifNull: ["$total_tokens", 0] } }
        }
      },
      {
        $project: {
          date: "$_id",
          messageCount: 1,
          tokenCount: 1,
          _id: 0
        }
      },
      { $sort: { date: 1 } }
    ]).toArray();

    // Fill in empty dates for dailyVolume if no messages occurred
    const dailyVolumeMap = new Map(dailyVolume.map(d => [d.date, d]));
    const filledDailyVolume = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const entry = dailyVolumeMap.get(dateStr) || { date: dateStr, messageCount: 0, tokenCount: 0 };
      filledDailyVolume.push(entry);
    }

    return NextResponse.json({
      success: true,
      stats: {
        totalUsers,
        activeUsers24h,
        totalMessages,
        totalTokens: tokenStats.totalTokens,
        totalPromptTokens: tokenStats.totalPromptTokens,
        totalCompletionTokens: tokenStats.totalCompletionTokens,
        avgResponseTime: Number((tokenStats.avgResponseTime || 0).toFixed(2)),
      },
      modelBreakdown,
      dailyVolume: filledDailyVolume
    });
  } catch (error: any) {
    console.error("Stats API error:", error);
    return NextResponse.json(
      { error: "Failed to load database stats: " + error.message },
      { status: 500 }
    );
  }
}
