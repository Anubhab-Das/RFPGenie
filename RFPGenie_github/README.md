### Backend Setup

1.  **Create and Activate Virtual Environment:**
    From the project root directory (`RFPGenie`), create a virtual environment.

    python -m venv .venv
    

    Activate the environment:
    source .venv/bin/activate
    

2.  **Install Dependencies:**
    Install the required Python packages.

    pip install -r backend/requirements.txt


3.  **Set Up Environment Variables:**
    Create a `.env` file in the project root directory, if not already present. This file will hold your secret keys and configuration settings.

    ```
    # .env
    DATABASE_URL=postgresql+asyncpg://postgres:12345678@localhost:5432/rfpgenie (change accordingly)
    SUPABASE_RAG_URL="your_supabase_project_url"
    SUPABASE_RAG_KEY="your_supabase_service_role_key"
    OPENAI_API_KEY=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
    GOOGLE_API_KEY=your-google-api-key (not needed, keep as it is)
    VITE_TINYMCE_API_KEY=bciem0i3s32eip7mcrzy0roct9ebloppfytqmnxbgopd8e5q

    # Optional:
    # FINAL_GENERATION_MODEL="gpt-4o-mini"
    # RAG_MATCH_THRESHOLD=0.3
    ```

    - **`DATABASE_URL`**: Your local PostgreSQL connection string.
    - **`SUPABASE_RAG_URL`**: The URL of your Supabase project. 
    Find this in your Supabase dashboard under `Project Settings > General` . 
    Copy the Project ID and paste it in this format "https://<project_id>.supabase.co" 
    For e.g. "https://djsmufkipzpmvnbeydel.supabase.co" 

    - **`SUPABASE_RAG_KEY`**: Your Supabase `service_role` key. Find this in your Supabase dashboard under `Project Settings > API- Keys` . Reveal and copy the service_role secret key.

4.  **Set Up Supabase Database:**
    You need to set up the necessary tables and functions in your Supabase project.
    - Go to your Supabase project dashboard.
    - Navigate to the **SQL Editor** (usually found in the left sidebar).
    - Copy and paste the exact content of "supabase_script.md" into the editor and run it.

 
5.  **Run the Backend Server:**
    Start the FastAPI server.

    uvicorn backend.main:app --reload


    The backend will be running at `http://127.0.0.1:8000`.

### Frontend Setup

1.  **Install Dependencies:**
    In a new terminal, navigate to the project root and install the required npm packages.

    npm install

2.  **Run the Frontend:**
    Start the Vite development server.

    npm run dev

    The frontend will be accessible at `http://localhost:5173` .

## Application Workflow

### 1. Setup Supabase Collections

The first step is to build your knowledge base.
- Click the **Upload** button next to the title.
- Upload a PDF or DOCX document. The system will process, chunk, and embed the content into vector collections in Supabase, making it available for proposal generation.

### 2. Create a Template

Templates define the structure of your proposals.
- Navigate to the **Templates** page.
- Click **Create Template** and give it a name.
- By default, a template includes five standard sections. You can customize these as needed.

### 3. Generate a Proposal

This is a two-stage process: drafting and finalization.

**Stage 1: Initial Draft**
1.  Navigate to the **Proposals** page and click **Create Proposal**.
2.  Provide a Proposal Name, Description, and Client Name.
3.  Upload the client's RFP document.
4.  Select a template to use for the structure.
5.  Click **Generate Proposal**. The AI will generate an initial draft based on the RFP and your chosen template sections.

**Stage 2: Refinement and Regeneration**
After the initial draft is created, you can refine each section:
- **Select Collections:** Use the dropdown menu to choose one or more of your knowledge collections. The AI will use these as a primary source for regeneration.
- **Manual Editing:** Click the **pencil icon** to edit the content of a section directly.
- **Regenerate with Prompt:** Click the **refresh icon** and enter a custom prompt.
- **Quick Regenerate:** Click the **sparkle icon** to regenerate the section based on the current draft context, custom prompt if any and selected collections if any.
- **Versioning:** A new version of the section is created with each regeneration, allowing you to switch between different iterations. The version you are currently viewing is the one that will be used in the final document.

**Stage 3: Final Proposal**
- Once you are satisfied with all the sections, click the **Generate Final Proposal** button.
- The system will compile the selected versions of all sections into a single document.
- You can perform final edits in the TinyMCE rich text editor and then download the proposal as a PDF.

### 4. Managing Assets

- **Collections:** Delete a knowledge source by clicking the **trash bin icon** on the Collections page. This will remove the source document and all its associated content from Supabase.
- **Templates:** Delete a template by clicking on its card and then clicking the **trash bin icon**.
  - *Note:* You cannot delete a template that is currently linked to a proposal in the "drafting" state.
- **Proposals:** Delete a proposal from any state (draft or final) by clicking on its card and then clicking the **delete icon**.

