from app.cron_jobs.update_members_mysql import sync_members


def back_fill_members():
    result = sync_members()
    print(f"read {result['read']}")
    print(f"written {result['written']}")
    print(f"skipped {result['skipped']}")
    print(f"without dpi {result['without_dpi']}")
    return result


if __name__ == "__main__":
    back_fill_members()
