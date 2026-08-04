from app.cron_jobs.sync_members_salesforce import sync_members_salesforce


def back_fill_members_salesforce():
    result = sync_members_salesforce()
    print(f"members {result['members']}")
    print(f"matched {result['matched']}")
    print(f"written {result['written']}")
    print(f"without contract {result['without_contract']}")
    print(f"without account {result['without_account']}")
    print(f"empty {result['empty']}")
    return result


if __name__ == "__main__":
    back_fill_members_salesforce()
