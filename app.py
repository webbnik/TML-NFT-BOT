from nft import app
import subprocess

if __name__ == "__main__":
    # Initialize the database
    with app.app_context():
        try:
            subprocess.run(["flask", "db", "init"])
        except Exception as e:
            print(f"An error occurred during database initialization: {str(e)}")
        
        subprocess.run(["flask", "db", "migrate"])
        subprocess.run(["flask", "db", "upgrade"])
        fetchbinance()
        fetch_magiceden()
    app.run(host="0.0.0.0", port=8457, debug=False)
