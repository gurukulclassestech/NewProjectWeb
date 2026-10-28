# Here are your Instructions

## Deploying to Vercel

Deploy the frontend and backend as two Vercel projects from this repository:

1. Create a backend project with the Root Directory set to `backend`. Vercel uses `backend/api/[...path].py` as the FastAPI entry point and installs dependencies from `backend/requirements.txt`.
2. Set these backend environment variables in Vercel for every environment you use:
	- `MONGO_URL`: a reachable MongoDB connection string, such as a MongoDB Atlas URI.
	- `DB_NAME`: the production database name.
	- `USE_MOCK_DB=0`: use the persistent MongoDB database rather than a local/mock database.
	- `JWT_SECRET`: a long, unique random secret.
	- `ADMIN_USERNAME` and `ADMIN_PASSWORD`: secure initial credentials for the first admin created in an empty database. The legacy defaults are `admin` / `admin@123` if these are omitted.
3. Create a frontend project from the same repository with the Root Directory set to `frontend`. Set `REACT_APP_API_URL` to `https://<your-backend-project>.vercel.app/api` before deploying. CRA embeds this value at build time, so redeploy after changing it.
4. The backend health message is available at `https://<your-backend-project>.vercel.app/api/`.

The current image-upload endpoint writes to the backend's local `uploads/` directory. Vercel function filesystems are temporary and may be read-only, so uploaded images are not durable and uploads may fail there. Configure object storage and update the upload endpoint before relying on image uploads in production. Existing files in `backend/uploads/` should also be moved to durable storage if the site needs them after deployment.
