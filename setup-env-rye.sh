set -e

cd "$(dirname $0)"

echo "Use rye to manage python environment"

# check if rye is installed
if ! command -v rye &> /dev/null
then
    echo "Installing rye ..."
    curl -sSf https://rye-up.com/get | bash --yes
    echo "rye docs: https://rye-up.com/"
fi

rye sync

echo "SETUP: install pre-commit hooks"
pre-commit install

echo "Try running 'python recoverable_async_task.py' to test your setup"
