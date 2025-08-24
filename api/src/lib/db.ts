import mongoose from "mongoose";
export async function connectDB(uri?: string) {
  const MONGO_URI = uri || process.env.MONGO_URI || "mongodb://localhost:27017/surv";
  await mongoose.connect(MONGO_URI);
  console.log("Mongo connected:", MONGO_URI);
}
