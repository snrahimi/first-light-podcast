"""Small self-contained RSS fixture for integration tests."""
def editorial_groups():
    def item(title,section,publisher,age):
        from urllib.parse import quote
        return {"title":title, "category":section, "publisher":publisher,
                "summary":title, "url":"https://example.org/"+quote(title),
                "age":age, "published":"2026-11-23T09:30:00+00:00"}
    return {
        "world":[
            item("Ukraine peace talks continue as European leaders meet","world","BBC",1),
            item("European leaders meet to continue Ukraine peace talks","world","NPR",2),
            item("Japan election results bring parliamentary coalition discussions","world","Guardian",3),
            item("Brazil leaders negotiate new regional trade agreement","world","Al Jazeera",4),
            item("Sudan relief agencies report humanitarian supplies delayed","world","BBC",5),
            item("Canada announces changes to national transport rules","world","NPR",6)],
        "business":[
            item("Global inflation pressures prompt central bank discussion","business","BBC",2)],
        "science":[
            item("Scientists publish new observations from Antarctic ice samples","science","NPR",3)],
        "tech":[
            item("Cybersecurity researchers disclose major software vulnerability","tech","BBC",2)],
    }
