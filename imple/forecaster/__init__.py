import os

# Set model cache dir to working dir's 'models' dir
model_path = os.path.join(os.path.abspath(os.getcwd()), "models")
os.environ["HF_HOME"] = model_path
os.environ["HF_HUB_CACHE"] = os.path.join(model_path, "hub")