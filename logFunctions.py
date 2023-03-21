from colorama import Fore, Back, Style
import datetime

bold = '\033[1m'
normal = "\033[0m"

def logDatetime():
    logTime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logTimeString = f"{Fore.LIGHTBLACK_EX}{bold}{logTime}{normal}"
    print(f"{logTimeString}", end=f"{Style.RESET_ALL} ")

def logInfo(message, group, end="\n"):
    logDatetime()
    groupString = f"{normal}{Fore.MAGENTA}{group}{Style.RESET_ALL}"
    print(f"{Fore.BLUE}{Style.BRIGHT}INFO{Style.RESET_ALL}     {groupString} {Style.RESET_ALL}{message}", end=end)

def logWarning(message, group, end="\n"):
    logDatetime()
    groupString = f"{normal}{Fore.MAGENTA}{group}{Style.RESET_ALL}"
    print(f"{Fore.YELLOW}{Style.BRIGHT}WARNING{Style.RESET_ALL}  {groupString} {Style.RESET_ALL}{message}", end=end)

def logError(message, group, end="\n"):
    logDatetime()
    groupString = f"{normal}{Fore.MAGENTA}{group}{Style.RESET_ALL}"
    print(f"{Fore.RED}{Style.BRIGHT}ERROR{Style.RESET_ALL}    {groupString} {Style.RESET_ALL}{message}", end=end)

if __name__ == "__main__":
    logInfo("This is a test", "testGroup")