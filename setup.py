#!/usr/bin/env python3
"""
Setup utility for AgentMail chatbot project.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_banner():
    """Print setup banner."""
    print("🤖 AgentMail AI Chatbot Setup")
    print("=" * 50)
    print("This utility will help you set up the AgentMail chatbot.")
    print()

def check_python_version():
    """Check Python version requirements."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def setup_virtual_environment():
    """Set up virtual environment."""
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    try:
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        
        # Get activation command
        if os.name == 'nt':  # Windows
            activate_cmd = "venv\\Scripts\\activate"
        else:  # Unix-like
            activate_cmd = "source venv/bin/activate"
        
        print(f"💡 To activate: {activate_cmd}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False

def install_dependencies():
    """Install Python dependencies."""
    try:
        print("📦 Installing dependencies...")
        
        # Try to use venv python if available
        python_cmd = sys.executable
        venv_python = Path("venv/bin/python")
        if venv_python.exists():
            python_cmd = str(venv_python)
        elif Path("venv/Scripts/python.exe").exists():
            python_cmd = str(Path("venv/Scripts/python.exe"))
        
        subprocess.run([
            python_cmd, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        
        print("✅ Dependencies installed")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def setup_config():
    """Set up configuration files."""
    config_dir = Path("config")
    env_file = config_dir / ".env"
    example_file = config_dir / ".env.example"
    
    if env_file.exists():
        print("✅ Configuration file already exists")
        return True
    
    if not example_file.exists():
        print("❌ Example configuration file not found")
        return False
    
    try:
        shutil.copy2(example_file, env_file)
        print("✅ Created configuration file from template")
        print(f"📝 Please edit {env_file} with your API keys")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create configuration file: {e}")
        return False

def show_next_steps():
    """Show next steps to user."""
    print("\n" + "=" * 50)
    print("🎉 Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Edit config/.env with your API keys:")
    print("   - AGENTMAIL_API_TOKEN")
    print("   - OPENAI_API_KEY") 
    print("   - WEBHOOK_URL")
    print("\n2. Test your setup:")
    print("   python examples/test_connection.py")
    print("\n3. Set up demo data:")
    print("   python examples/setup_demo.py")
    print("\n4. Run the chatbot server:")
    print("   python main.py")
    print("\n📖 See QUICKSTART.md for detailed instructions")

def main():
    """Main setup function."""
    print_banner()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Setup steps
    steps = [
        ("🌐 Setting up virtual environment", setup_virtual_environment),
        ("📦 Installing dependencies", install_dependencies),
        ("⚙️  Setting up configuration", setup_config),
    ]
    
    success = True
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        if not step_func():
            success = False
            break
    
    if success:
        show_next_steps()
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()