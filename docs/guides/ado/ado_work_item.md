# ADO Work Item (Board)

### Link work items to wiki page

**Prompt 1**
```
In wiki "WIKI" link work item ids (50, 49] to page "1/3".
```
Results:
- ![wi_link_case1_success](./images/wi_link_case1_success.jpg)

---
**Prompt 2**

```
In wiki "non-existing" link work items [50, 49] to page "1".
```
Results:
- ![wi_link_case2_wiki_nonexisting](./images/wi_link_case2_wiki_nonexisting.jpg)

---
**Prompt 3**
```
In wiki "WIKI" link work items ids (50, 49] to page "non-existing-page".
```
Results:
- ![wi_link_case3_page_nonexisting](./images/wi_link_case3_page_nonexisting.jpg)

---
**Prompt 4**

```
In wiki "WIKI" link work items [50, 23423423] to page "1/3"
```
Results:
- ![wi_link_case4_id_nonexisting](./images/wi_link_case4_id_nonexisting.jpg)

---
**Prompt 5**

```
In wiki "WIKI" link work items [] to page "1/3"
```
Results:
- ![wi_link_case5_empty_list](./images/wi_link_case5_empty_list.jpg)


### Unlink work items from wiki page
---
**Prompt 6**

```
In wiki "WIKI" unlink work item ids [50] from page "1/3"
```

Results:
- ![wi_unlink_case6_success](./images/wi_unlink_case6_success.jpg)