import { MongoClient } from "mongodb";

const dbName = process.env.DATABASE_NAME || "telegram_ai_bot";

let client: MongoClient;
let clientPromise: Promise<MongoClient> | null = null;

export async function getDb() {
  const uri = process.env.MONGODB_URI;
  if (!uri) {
    throw new Error("Please add your MONGODB_URI to environment variables");
  }

  if (!clientPromise) {
    if (process.env.NODE_ENV === "development") {
      // In development mode, use a global variable so that the value
      // is preserved across module reloads caused by HMR (Hot Module Replacement).
      const globalWithMongo = global as typeof globalThis & {
        _mongoClientPromise?: Promise<MongoClient>;
      };

      if (!globalWithMongo._mongoClientPromise) {
        client = new MongoClient(uri);
        globalWithMongo._mongoClientPromise = client.connect();
      }
      clientPromise = globalWithMongo._mongoClientPromise;
    } else {
      // In production mode, it's best to not use a global variable.
      client = new MongoClient(uri);
      clientPromise = client.connect();
    }
  }

  const connection = await clientPromise;
  return connection.db(dbName);
}
